import sys
import time
import pytz
import os
from datetime import datetime
import matplotlib.pyplot as plt

from utils import (
    get_daily_papers_by_keyword_with_retries,
    generate_table,
    back_up_files,
    restore_files,
    remove_backups,
    get_daily_date,
    write_papers_to_file,
    count_papers_by_keyword,
    write_keyword_statistics,
    generate_monthly_stats_plot,
    read_all_existing_papers,
)


def main():
    try:
        beijing_timezone = pytz.timezone("Asia/Singapore")
        current_date = datetime.now(beijing_timezone)

        # Create papers directory if it doesn't exist
        os.makedirs("papers", exist_ok=True)
        for keyword in keywords:
            os.makedirs(
                os.path.join("papers", keyword.replace(" ", "_").lower()), exist_ok=True
            )

        # Backup files before making any changes
        back_up_files()

        # Read existing papers
        existing_papers = read_all_existing_papers()

        # request new papers
        for keyword in keywords:
            if len(keyword.split()) == 1:
                link = "AND"  # for keyword with only one word
            else:
                link = "OR"
            papers = get_daily_papers_by_keyword_with_retries(
                keyword, column_names, max_result, link
            )
            if papers is None:
                raise Exception(f"Failed to get papers for keyword: {keyword}")

            papers = sorted(papers, key=lambda x: x["Date"], reverse=True)

            existing_papers_by_keyword_links = [
                paper["Link"] for paper in existing_papers[keyword]
            ]
            # merge papers with existing papers by link
            new_papers = [
                paper
                for paper in papers
                if paper["Link"] not in existing_papers_by_keyword_links
            ]

            # write papers to files
            filepath = write_papers_to_file(
                new_papers, existing_papers[keyword], keyword, current_date
            )
            if filepath is None:
                raise Exception(f"Failed to write papers for keyword: {keyword}")

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
                latest_month_str = (
                    f"{latest_month[0]} ({latest_month[1]} papers)"
                    if latest_month[0]
                    else "No papers"
                )
                f_rm.write(f"| {keyword} | {stats['total']} | {latest_month_str} |\n")

            f_rm.write("\n## Monthly Trends\n\n")

            # Generate and save plots for each keyword
            for keyword in keywords:
                stats = count_papers_by_keyword(keyword)
                if stats["total"] > 0:
                    fig = generate_monthly_stats_plot(stats, keyword)
                    plot_path = os.path.join(
                        "papers", keyword.replace(" ", "_").lower(), "monthly_stats.png"
                    )
                    fig.savefig(plot_path)
                    plt.close(fig)

                # Write statistics markdown file
                stats_path = os.path.join(
                    "papers", keyword.replace(" ", "_").lower(), "README.md"
                )
                with open(stats_path, "w", encoding="utf-8") as f:
                    f.write(f"# Statistics for {keyword}\n\n")

                    # Overall statistics
                    f.write("## Overall Statistics\n\n")
                    f.write(f"- Total number of papers: {stats['total']}\n")
                    f.write(f"- Number of months tracked: {len(stats['months'])}\n")
                    if stats["total"] > 0:
                        avg_papers = stats["total"] / len(stats["months"])
                        f.write(f"- Average papers per month: {avg_papers:.1f}\n")

                    # Monthly trend visualization
                    f.write("\n## Monthly Trends\n\n")
                    f.write(f"![Monthly Paper Counts](monthly_stats.png)\n\n")

                    # Detailed monthly breakdown
                    f.write("## Monthly Breakdown\n\n")
                    f.write("| Month | Paper Count | Percentage of Total |\n")
                    f.write("| --- | --- | --- |\n")

                    # Sort months in reverse chronological order
                    sorted_months = sorted(stats["months"].keys(), reverse=True)
                    for month in sorted_months:
                        count = stats["months"][month]
                        percentage = (
                            (count / stats["total"] * 100) if stats["total"] > 0 else 0
                        )
                        f.write(f"| {month} | {count} | {percentage:.1f}% |\n")

                    # Add plot to README
                    relative_path = os.path.relpath(plot_path)
                    f_rm.write(f"### {keyword}\n\n")
                    f_rm.write(
                        f"![Monthly Paper Counts for {keyword}]({relative_path})\n\n"
                    )

        # If everything succeeded, remove backups
        remove_backups()

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        restore_files()
        sys.exit(1)


if __name__ == "__main__":
    keywords = ["gaussian splatting", "embodied ai", "llm"]
    max_result = 100
    column_names = ["Title", "Link", "Abstract", "Date", "Comment"]
    main()
