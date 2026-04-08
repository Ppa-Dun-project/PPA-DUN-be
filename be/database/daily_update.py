# daily_update.py — 매일 새벽에 실행하는 데이터 업데이트 스크립트.
# injury, depth_charts, transactions 3개를 순차적으로 업데이트한다.
#
# 사용법:
#   1) 직접 실행:  python daily_update.py
#   2) 스케줄러:   python daily_update.py --scheduled  (매일 3AM ET 자동 실행)
#   3) 외부 cron:  cron이나 Cloud Scheduler에서 1번 방식으로 호출
import argparse
import logging
import sys
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_daily_update():
    """injury, depth_charts, transactions를 순차적으로 업데이트한다."""
    start = datetime.now()
    logger.info("=== Daily update started ===")
    results = {}

    # 1. Injuries
    try:
        logger.info("[1/3] Updating injuries...")
        from be.database.injury import fetch_and_store as update_injuries
        update_injuries()
        results["injuries"] = "OK"
    except Exception as e:
        logger.error(f"[1/3] Injuries failed: {e}")
        results["injuries"] = f"FAILED: {e}"

    # 2. Depth Charts
    try:
        logger.info("[2/3] Updating depth charts...")
        from be.database.depth_charts import fetch_and_store as update_depth_charts
        update_depth_charts()
        results["depth_charts"] = "OK"
    except Exception as e:
        logger.error(f"[2/3] Depth charts failed: {e}")
        results["depth_charts"] = f"FAILED: {e}"

    # 3. Transactions
    try:
        logger.info("[3/3] Updating transactions...")
        from be.database.transactions import fetch_and_store as update_transactions
        update_transactions()
        results["transactions"] = "OK"
    except Exception as e:
        logger.error(f"[3/3] Transactions failed: {e}")
        results["transactions"] = f"FAILED: {e}"

    elapsed = (datetime.now() - start).total_seconds()
    logger.info(f"=== Daily update finished in {elapsed:.1f}s ===")
    for name, status in results.items():
        logger.info(f"  {name}: {status}")

    return results


def run_scheduled():
    """매일 3AM ET에 자동 실행하는 스케줄러 모드."""
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.error("apscheduler가 필요합니다: pip install apscheduler")
        sys.exit(1)

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_daily_update,
        trigger=CronTrigger(hour=3, minute=0, timezone="EST"),
        id="daily_update",
        name="Daily MLB data update (3AM ET)",
    )
    logger.info("Scheduler started — next run at 3:00 AM EST daily")
    logger.info("Press Ctrl+C to stop")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily MLB data updater")
    parser.add_argument("--scheduled", action="store_true", help="Run as scheduler (3AM ET daily)")
    args = parser.parse_args()

    if args.scheduled:
        run_scheduled()
    else:
        run_daily_update()
