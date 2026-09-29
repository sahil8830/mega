"""
Run the indexing pipeline directly (outside uvicorn) to capture the full traceback.
"""
import asyncio
import sys
import os
import traceback

sys.path.insert(0, '.')

# Set env vars
os.environ.setdefault('MONGODB_URI', 'mongodb://localhost:27017/mega')
os.environ.setdefault('VIDEO_STORAGE_PATH', '../backend/storage/videos')
os.environ.setdefault('FAISS_INDEX_PATH', './faiss')

VIDEO_ID = '6abb8dcd8716ebc99ce0d8a1'
VIDEO_FILENAME = '1790676428961-71067487.mp4'
USER_ID = '6abb77ec1ccfc9c55cb1a9ec'

async def main():
    print(f"\n{'='*60}")
    print(f"Running indexing pipeline directly for debugging")
    print(f"Video: {VIDEO_FILENAME}")
    print(f"User:  {USER_ID}")
    print(f"{'='*60}\n")

    try:
        from app.services.indexing_pipeline import run_indexing_pipeline
        result = await run_indexing_pipeline(
            video_id=VIDEO_ID,
            video_filename=VIDEO_FILENAME,
            user_id=USER_ID,
        )
        print(f"\nResult: {result}")
    except Exception as e:
        print(f"\n❌ EXCEPTION: {type(e).__name__}: {e}")
        traceback.print_exc()

asyncio.run(main())
