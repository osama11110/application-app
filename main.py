"""
Job Application Automation — Austria
Usage:
  python main.py                     # run all enabled sites
  python main.py --dry-run           # search only, no submissions
  python main.py --site linkedin     # run one site only
  python main.py --reset-cv-cache    # re-parse CV even if cached
"""
import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

import yaml
from colorama import Fore, Style, init as colorama_init
from playwright.async_api import async_playwright

from cv_parser import parse_cv
from ai_helper import AIHelper
from tracker import init_db, has_applied, record_application, get_daily_count, get_summary
from sites import SITE_MAP

colorama_init(autoreset=True)

# ------------------------------------------------------------------ logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"logs/run_{time.strftime('%Y%m%d_%H%M%S')}.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")


# ------------------------------------------------------------------ helpers
def load_config(path: str = "config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_config(cfg: dict):
    if not cfg.get("anthropic_api_key"):
        print(Fore.RED + "\n[ERROR] anthropic_api_key is empty in config.yaml")
        print("  Get one at: https://console.anthropic.com\n")
        sys.exit(1)
    cv = cfg.get("cv_path", "cv/cv.pdf")
    if not Path(cv).exists():
        print(Fore.RED + f"\n[ERROR] CV not found: {cv}")
        print("  Place your CV (PDF or DOCX) at that path.\n")
        sys.exit(1)


def banner():
    print(Fore.CYAN + """
╔══════════════════════════════════════════════════════╗
║     Job Application Automation — Austria             ║
║     Powered by Playwright + Claude AI                ║
╚══════════════════════════════════════════════════════╝
""")


def print_job(job: dict, score: int, status: str):
    color = Fore.GREEN if status == "applying" else (Fore.YELLOW if status == "skip" else Fore.RED)
    print(f"  {color}[{status.upper():8s}] {Fore.WHITE}{job['title'][:45]:<45} "
          f"{Fore.CYAN}{job['company'][:30]:<30} {Fore.MAGENTA}score={score}")


# ------------------------------------------------------------------ core
async def run_site(site_name: str, SiteClass, page, config: dict, cv_data: dict, ai: AIHelper):
    creds = config["credentials"].get(site_name, {})
    if not creds.get("enabled", True):
        logger.info(f"Skipping {site_name} (disabled in config)")
        return

    site = SiteClass(page, config, cv_data)
    app_cfg = config.get("application", {})
    max_per_day = app_cfg.get("max_applications_per_day", 40)
    delay_s = app_cfg.get("delay_between_applications_seconds", 45)
    min_score = app_cfg.get("min_match_score", 55)
    dry_run = app_cfg.get("dry_run", False)
    gen_cl = app_cfg.get("generate_cover_letter", True)

    print(Fore.YELLOW + f"\n{'═'*60}")
    print(Fore.YELLOW + f"  Site: {site_name.upper()}")
    print(Fore.YELLOW + f"{'═'*60}")

    if not await site.login():
        print(Fore.RED + f"  Login failed for {site_name} — skipping")
        return

    keywords = cv_data.get("job_titles_to_search", [])
    if not keywords:
        keywords = cv_data.get("keywords", [])[:8]

    jobs = await site.search_jobs(keywords, config["search"].get("location", "Austria"))
    print(f"  Found {len(jobs)} jobs")

    applied_count = 0
    for job in jobs:
        if get_daily_count() >= max_per_day:
            print(Fore.YELLOW + f"  Daily limit ({max_per_day}) reached — stopping")
            break

        if has_applied(site_name, job["url"]):
            continue

        score = ai.score_job_match(cv_data, job)

        if score < min_score:
            print_job(job, score, "skip")
            record_application(site_name, job["url"], job["company"], job["title"],
                               "skipped_low_score", score, job.get("location", ""))
            continue

        print_job(job, score, "applying")

        cover_letter = ""
        if gen_cl and not dry_run:
            try:
                cover_letter = ai.generate_cover_letter(cv_data, job)
            except Exception as e:
                logger.warning(f"Cover letter generation failed: {e}")

        try:
            success = await site.apply_to_job(job, cover_letter)
            status = "applied" if success else "failed"
            record_application(site_name, job["url"], job["company"], job["title"],
                               status, score, job.get("location", ""))
            if success:
                applied_count += 1
                await asyncio.sleep(delay_s)
        except Exception as e:
            logger.error(f"apply_to_job error ({job['title']}): {e}")
            record_application(site_name, job["url"], job["company"], job["title"],
                               "error", score, job.get("location", ""), str(e))

    print(f"  {Fore.GREEN}Applied: {applied_count} / {len(jobs)} jobs on {site_name}")


async def main(args):
    banner()
    config = load_config()
    validate_config(config)

    if args.reset_cv_cache:
        cached = Path("cv/parsed_cv.json")
        if cached.exists():
            cached.unlink()
            print("CV cache cleared — will re-parse")

    if args.dry_run:
        config.setdefault("application", {})["dry_run"] = True
        print(Fore.YELLOW + "[DRY RUN mode — no applications will be submitted]\n")

    print("Parsing CV...")
    cv_data = parse_cv(config["cv_path"], config["anthropic_api_key"])
    print(f"  {Fore.GREEN}Name: {cv_data['personal'].get('name')}")
    print(f"  {Fore.GREEN}Search titles: {', '.join(cv_data.get('job_titles_to_search', [])[:5])}...")

    ai = AIHelper(config["anthropic_api_key"])
    init_db()

    # Which sites to run
    sites_to_run = {k: v for k, v in SITE_MAP.items()
                    if not args.site or k == args.site}
    if not sites_to_run:
        print(Fore.RED + f"Unknown site: {args.site}. Options: {', '.join(SITE_MAP.keys())}")
        return

    app_cfg = config.get("application", {})
    headless = app_cfg.get("headless", False)

    # Persistent profile keeps cookies/sessions between runs — sites see a returning user
    profile_dir = os.path.abspath("browser_profile")
    os.makedirs(profile_dir, exist_ok=True)
    print(f"  {Fore.CYAN}Browser profile: {profile_dir}")

    async with async_playwright() as pw:
        # launch_persistent_context saves cookies, localStorage, and session data
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=headless,
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="de-AT",
            timezone_id="Europe/Vienna",
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )

        # Apply stealth patches
        try:
            from playwright_stealth import stealth_async
            page = await context.new_page()
            await stealth_async(page)
        except ImportError:
            logger.warning("playwright-stealth not installed — running without stealth")
            page = await context.new_page()

        for site_name, SiteClass in sites_to_run.items():
            try:
                await run_site(site_name, SiteClass, page, config, cv_data, ai)
            except Exception as e:
                logger.error(f"Fatal error on {site_name}: {e}", exc_info=True)

        await context.close()

    # Final summary
    print(Fore.CYAN + f"\n{'═'*60}")
    print(Fore.CYAN + "  SUMMARY")
    print(Fore.CYAN + f"{'═'*60}")
    summary = get_summary()
    total_applied = 0
    for site, counts in summary.items():
        applied = counts.get("applied", 0)
        total_applied += applied
        print(f"  {site:20s}  applied={applied}  skipped={counts.get('skipped_low_score',0)}  "
              f"failed={counts.get('failed',0)+counts.get('error',0)}")
    print(Fore.GREEN + f"\n  Total applications submitted today: {get_daily_count()}")
    print(Fore.GREEN + f"  Total all-time applied: {total_applied}")
    print(f"\n  Full log: logs/")
    print(f"  Application database: applications.db\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Austrian Job Application Automation")
    parser.add_argument("--dry-run", action="store_true", help="Search only, don't submit")
    parser.add_argument("--site", type=str, default=None,
                        help=f"Run one site only: {', '.join(SITE_MAP.keys())}")
    parser.add_argument("--reset-cv-cache", action="store_true", help="Re-parse CV")
    args = parser.parse_args()
    asyncio.run(main(args))
