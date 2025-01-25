import sys
import time
import pytz
import os
from datetime import datetime

from utils import (
    get_daily_papers_by_keyword_with_retries,
    generate_table,
    back_up_files,
    restore_files,
    remove_backups,
    get_daily_date,
    write_papers_to_file,
    count_papers_by_keyword,
)


beijing_timezone = pytz.timezone("Asia/Singapore")

# NOTE: arXiv API seems to sometimes return an unexpected empty list.

# get current beijing time date in the format of "2021-08-01"
current_date = datetime.now(beijing_timezone)
# get last update date from README.md
with open("README.md", "r") as f:
    while True:
        line = f.readline()
        if "Last update:" in line:
            break
    last_update_date = line.split(": ")[1].strip()
    # if last_update_date == current_date:
    # sys.exit("Already updated today!")

keywords = ["gaussian splatting", "embodied ai", "llm"]

max_result = 100  # maximum query results from arXiv API for each keyword

# all columns: Title, Authors, Abstract, Link, Tags, Comment, Date
# fixed_columns = ["Title", "Link", "Date"]

column_names = ["Title", "Link", "Abstract", "Date", "Comment"]

back_up_files()  # back up README.md and ISSUE_TEMPLATE.md

# Create papers directory if it doesn't exist
os.makedirs("papers", exist_ok=True)

# Write to README.md
with open("README.md", "w") as f_rm:
    f_rm.write("# Daily arXiv Papers\n")
    f_rm.write(
        "This project automatically tracks and organizes the latest arXiv papers on specific research topics.\n\n"
    )
    f_rm.write(
        "Papers are organized by keywords (like 'gaussian splatting', 'embodied ai', 'llm') and grouped by month.\n\n"
    )
    f_rm.write(
        "Each monthly directory contains up to 100 papers per file for better readability.\n\n"
    )
    f_rm.write(
        "Click 'Watch' in the top right to receive notifications when new papers are added.\n\n"
    )
    f_rm.write(f"Last update: {current_date.strftime('%Y-%m-%d')}\n\n")
    
    # Add paper statistics
    f_rm.write("## Statistics\n\n")
    f_rm.write("| Keyword | Total Papers | Latest Month Papers |\n")
    f_rm.write("| --- | --- | --- |\n")
    
    for keyword in keywords:
        stats = count_papers_by_keyword(keyword)
        latest_month = next(iter(stats["months"].items()), (None, 0))
        latest_month_str = f"{latest_month[0]} ({latest_month[1]} papers)" if latest_month[0] else "No papers"
        
        f_rm.write(f"| {keyword} | {stats['total']} | {latest_month_str} |\n")
    
    f_rm.write("\n## Papers\n\n")

for keyword in keywords:
    if len(keyword.split()) == 1:
        link = "AND"  # for keyword with only one word
    else:
        link = "OR"

    papers = get_daily_papers_by_keyword_with_retries(
        keyword, column_names, max_result, link
    )
    if papers is None:
        print("Failed to get papers!")
        f_rm.close()
        restore_files()
        sys.exit("Failed to get papers!")

    # Sort papers by date
    papers = sorted(papers, key=lambda x: x["Date"], reverse=True)

    # Write papers to keyword-specific file
    filepath = write_papers_to_file(papers, keyword, current_date)
    
    # Add link to README if we have a valid filepath
    if filepath:
        with open("README.md", "a") as f_rm:
            relative_path = os.path.relpath(filepath)
            f_rm.write(f"## [{keyword}]({relative_path})\n\n")

    time.sleep(5)  # avoid being blocked by arXiv API

f_rm.close()
remove_backups()
