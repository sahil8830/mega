import asyncio
import unittest
from unittest.mock import patch
from fastapi import BackgroundTasks
from app.routes import index_route as route


class IndexQueueTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        route._indexing_lock = asyncio.Lock()
        route._pending_videos.clear()

    async def test_index_and_reindex_never_overlap(self):
        entered = asyncio.Event()
        release = asyncio.Event()
        order = []

        async def index(**kwargs):
            order.append("index")
            entered.set()
            await release.wait()

        async def reindex(*args):
            order.append("reindex")

        with patch("app.services.indexing_pipeline.run_indexing_pipeline", index), \
             patch.object(route, "_run_reindex", reindex):
            first = asyncio.create_task(route._pipeline_task("first", "a.mp4", "user"))
            await entered.wait()
            second = asyncio.create_task(route._reindex_task("second", "b.mp4", "user"))
            await asyncio.sleep(0)
            self.assertEqual(order, ["index"])
            release.set()
            await asyncio.gather(first, second)
            self.assertEqual(order, ["index", "reindex"])

    async def test_duplicate_submissions_schedule_only_one_task(self):
        request = route.IndexRequest(video_id="video", video_filename="a.mp4")
        tasks = BackgroundTasks()
        await route.index_video(request, tasks)
        await route.index_video(request, tasks)
        await route.reindex_video(request, tasks)
        self.assertEqual(len(tasks.tasks), 1)

    async def test_failure_releases_slot_and_pending_video(self):
        async def fail(**kwargs):
            raise RuntimeError("test failure")

        route._pending_videos.add("video")
        with patch("app.services.indexing_pipeline.run_indexing_pipeline", fail):
            with self.assertRaises(RuntimeError):
                await route._pipeline_task("video", "a.mp4", "user")
        self.assertNotIn("video", route._pending_videos)
        self.assertFalse(route._indexing_lock.locked())
