import os
import time
import pytz
import shutil
import datetime
from typing import List, Dict
import urllib, urllib.request

import feedparser
from easydict import EasyDict


def remove_duplicated_spaces(text: str) -> str:
    return " ".join(text.split())


def request_paper_with_arXiv_api(
    keyword: str, max_results: int, link: str = "OR"
) -> List[Dict[str, str]]:
    # keyword = keyword.replace(" ", "+")
    assert link in ["OR", "AND"], "link should be 'OR' or 'AND'"
    keyword = '"' + keyword + '"'
    url = "http://export.arxiv.org/api/query?search_query=ti:{0}+{2}+abs:{0}&max_results={1}&sortBy=lastUpdatedDate".format(
        keyword, max_results, link
    )
    url = urllib.parse.quote(url, safe="%/:=&?~#+!$,;'@()*[]")
    response = urllib.request.urlopen(url).read().decode("utf-8")
    feed = feedparser.parse(response)

    # NOTE default columns: Title, Authors, Abstract, Link, Tags, Comment, Date
    papers = []
    for entry in feed.entries:
        entry = EasyDict(entry)
        paper = {}  # Changed from EasyDict() to regular dict

        # title
        paper["Title"] = remove_duplicated_spaces(entry.title.replace("\n", " "))
        # abstract
        paper["Abstract"] = remove_duplicated_spaces(entry.summary.replace("\n", " "))
        # authors
        paper["Authors"] = [
            remove_duplicated_spaces(_["name"].replace("\n", " "))
            for _ in entry.authors
        ]
        # link
        paper["Link"] = remove_duplicated_spaces(entry.link.replace("\n", " "))
        # tags
        paper["Tags"] = [
            remove_duplicated_spaces(_["term"].replace("\n", " ")) for _ in entry.tags
        ]
        # comment
        paper["Comment"] = remove_duplicated_spaces(
            entry.get("arxiv_comment", "").replace("\n", " ")
        )
        # date
        try:
            # ArXiv dates are in format like '2024-01-25T19:37:43Z'
            paper["Date"] = datetime.datetime.strptime(
                entry.updated, "%Y-%m-%dT%H:%M:%SZ"
            ).strftime("%Y-%m-%d")
        except:
            paper["Date"] = (
                entry.updated
            )  # fallback to original format if parsing fails

        papers.append(paper)
    return papers


def filter_tags(
    papers: List[Dict[str, str]], target_fileds: List[str] = ["cs", "stat"]
) -> List[Dict[str, str]]:
    # filtering tags: only keep the papers in target_fileds
    results = []
    for paper in papers:
        tags = paper["Tags"]  # Changed from paper.Tags
        for tag in tags:
            if tag.split(".")[0] in target_fileds:
                results.append(paper)
                break
    return results


def get_daily_papers_by_keyword_with_retries(
    keyword: str,
    column_names: List[str],
    max_result: int,
    link: str = "OR",
    retries: int = 6,
) -> List[Dict[str, str]]:
    for _ in range(retries):
        papers = get_daily_papers_by_keyword(keyword, column_names, max_result, link)
        if len(papers) > 0:
            return papers
        else:
            print("Unexpected empty list, retrying...")
            time.sleep(60 * 30)  # wait for 30 minutes
    # failed
    return None


def get_daily_papers_by_keyword(
    keyword: str, column_names: List[str], max_result: int, link: str = "OR"
) -> List[Dict[str, str]]:
    # get papers
    papers = request_paper_with_arXiv_api(
        keyword, max_result, link
    )  # NOTE default columns: Title, Authors, Abstract, Link, Tags, Comment, Date
    # NOTE filtering tags: only keep the papers in cs field
    # TODO filtering more
    papers = filter_tags(papers)
    # select columns for display
    papers = [
        {column_name: paper[column_name] for column_name in column_names}
        for paper in papers
    ]
    return papers


def generate_table(papers: List[Dict[str, str]], ignore_keys: List[str] = []) -> str:
    formatted_papers = []
    keys = papers[0].keys()
    for paper in papers:
        # process fixed columns
        formatted_paper = EasyDict()
        ## Title and Link
        formatted_paper.Title = (
            "**" + "[{0}]({1})".format(paper["Title"], paper["Link"]) + "**"
        )
        ## Process Date (format: 2021-08-01T00:00:00Z -> 2021-08-01)
        formatted_paper.Date = paper["Date"].split("T")[0]

        # process other columns
        for key in keys:
            if key in ["Title", "Link", "Date"] or key in ignore_keys:
                continue
            elif key == "Abstract":
                # add show/hide button for abstract
                formatted_paper[key] = (
                    "<details><summary>Show</summary><p>{0}</p></details>".format(
                        paper[key]
                    )
                )
            elif key == "Authors":
                # NOTE only use the first author
                formatted_paper[key] = paper[key][0] + " et al."
            elif key == "Tags":
                tags = ", ".join(paper[key])
                if len(tags) > 10:
                    formatted_paper[key] = (
                        "<details><summary>{0}...</summary><p>{1}</p></details>".format(
                            tags[:5], tags
                        )
                    )
                else:
                    formatted_paper[key] = tags
            elif key == "Comment":
                if paper[key] == "":
                    formatted_paper[key] = ""
                elif len(paper[key]) > 20:
                    formatted_paper[key] = (
                        "<details><summary>{0}...</summary><p>{1}</p></details>".format(
                            paper[key][:5], paper[key]
                        )
                    )
                else:
                    formatted_paper[key] = paper[key]
        formatted_papers.append(formatted_paper)

    # generate header
    columns = formatted_papers[0].keys()
    # highlight headers
    columns = ["**" + column + "**" for column in columns]
    header = "| " + " | ".join(columns) + " |"
    header = (
        header
        + "\n"
        + "| "
        + " | ".join(["---"] * len(formatted_papers[0].keys()))
        + " |"
    )
    # generate the body
    body = ""
    for paper in formatted_papers:
        body += "\n| " + " | ".join(paper.values()) + " |"
    return header + body


def back_up_files():
    # back up README.md and ISSUE_TEMPLATE.md
    shutil.move("README.md", "README.md.bk")


def restore_files():
    # restore README.md and ISSUE_TEMPLATE.md
    shutil.move("README.md.bk", "README.md")


def remove_backups():
    # remove README.md and ISSUE_TEMPLATE.md
    os.remove("README.md.bk")


def get_daily_date():
    # get beijing time in the format of "March 1, 2021"
    beijing_timezone = pytz.timezone("Asia/Singapore")
    today = datetime.datetime.now(beijing_timezone)
    return today.strftime("%B %d, %Y")


def get_paper_directory(keyword: str, paper_date: str) -> str:
    """Create and return path to directory for storing papers by keyword and upload date"""
    # Convert keyword to valid directory name
    keyword_dir = keyword.replace(" ", "_").lower()

    # Parse paper date (format: YYYY-MM-DD)
    date = datetime.datetime.strptime(paper_date, "%Y-%m-%d")

    # Create path like papers/gaussian_splatting/2025_01/
    paper_dir = os.path.join("papers", keyword_dir, f"{date.year}_{date.month:02d}")

    # Create directories if they don't exist
    os.makedirs(paper_dir, exist_ok=True)

    return paper_dir


def write_papers_to_file(papers: List[Dict[str, str]], keyword: str, _: datetime) -> str:
    """Write papers to markdown files organized by keyword and upload date, with max 100 papers per file"""
    # Sort papers by date in descending order (newest first)
    sorted_papers = sorted(papers, key=lambda x: x["Date"], reverse=True)
    
    # Group papers by month
    paper_groups = {}
    for paper in sorted_papers:
        paper_date = paper["Date"]
        paper_dir = get_paper_directory(keyword, paper_date)
        
        # Read existing papers for this month
        existing_papers = read_existing_papers(paper_dir)
        
        # Filter out papers that already exist
        new_papers = filter_new_papers([paper], existing_papers)
        if not new_papers:
            continue
            
        if paper_dir not in paper_groups:
            paper_groups[paper_dir] = existing_papers
        paper_groups[paper_dir].extend(new_papers)
    
    # If no new papers were added, return the most recent existing file
    if not paper_groups:
        # Find the most recent file
        keyword_dir = keyword.replace(" ", "_").lower()
        base_dir = os.path.join("papers", keyword_dir)
        if not os.path.exists(base_dir):
            # If no papers exist at all, create an empty file
            paper_dir = get_paper_directory(keyword, sorted_papers[0]["Date"])
            filepath = os.path.join(paper_dir, "papers.md")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# {keyword}\n\n")
                table = generate_table(sorted_papers)
                f.write(table)
            return filepath
            
        # Find most recent month directory
        months = sorted(os.listdir(base_dir), reverse=True)
        if not months:
            return None
            
        recent_dir = os.path.join(base_dir, months[0])
        files = [f for f in os.listdir(recent_dir) if f.endswith('.md')]
        if not files:
            return None
            
        # Return first file (should be papers.md or papers_1.md)
        return os.path.join(recent_dir, sorted(files)[0])
    
    # Write each month's papers to files
    first_filepath = None
    for paper_dir, month_papers in paper_groups.items():
        # Sort all papers by date
        month_papers = sorted(month_papers, key=lambda x: x["Date"], reverse=True)
        
        # Split papers into chunks of 100
        papers_per_file = 100
        num_files = (len(month_papers) + papers_per_file - 1) // papers_per_file
        
        for i in range(num_files):
            start_idx = i * papers_per_file
            end_idx = min((i + 1) * papers_per_file, len(month_papers))
            current_papers = month_papers[start_idx:end_idx]
            
            # Generate filename
            filename = f"papers_{i+1}.md" if num_files > 1 else "papers.md"
            filepath = os.path.join(paper_dir, filename)
            
            # Store first filepath to return (for README link)
            if first_filepath is None:
                first_filepath = filepath
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# {keyword}\n\n")
                # Add navigation links if there are multiple files
                if num_files > 1:
                    f.write("## Navigation\n\n")
                    for j in range(num_files):
                        nav_filename = f"papers_{j+1}.md" if num_files > 1 else "papers.md"
                        if j == i:
                            f.write(f"- Part {j+1}\n")
                        else:
                            f.write(f"- [Part {j+1}]({nav_filename})\n")
                    f.write("\n## Papers\n\n")
                
                table = generate_table(current_papers)
                f.write(table)
    
    return first_filepath


def read_existing_papers(paper_dir: str) -> List[Dict[str, str]]:
    """Read existing papers from all markdown files in the directory"""
    existing_papers = []
    if not os.path.exists(paper_dir):
        return existing_papers
        
    # Read all markdown files in directory
    for filename in os.listdir(paper_dir):
        if not filename.endswith('.md'):
            continue
            
        filepath = os.path.join(paper_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Extract paper information from markdown table
        # Skip header lines
        lines = content.split('\n')
        table_start = False
        for line in lines:
            if line.startswith('| **Title**'):
                table_start = True
                continue
            if table_start and line.startswith('| **['):
                # Parse paper info from table row
                cells = line.split('|')
                title = cells[1].strip().replace('**[', '').split('](')[0]
                link = cells[1].strip().split('](')[1].split(')')[0]
                date = cells[2].strip()
                
                paper = {
                    'Title': title,
                    'Link': link,
                    'Date': date
                }
                existing_papers.append(paper)
                
    return existing_papers


def filter_new_papers(new_papers: List[Dict[str, str]], existing_papers: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Filter out papers that already exist in the directory"""
    existing_links = {paper['Link'] for paper in existing_papers}
    return [paper for paper in new_papers if paper['Link'] not in existing_links]


def count_papers_by_keyword(keyword: str) -> Dict[str, int]:
    """Count total papers and papers by month for a given keyword"""
    keyword_dir = keyword.replace(" ", "_").lower()
    base_dir = os.path.join("papers", keyword_dir)
    
    if not os.path.exists(base_dir):
        return {"total": 0, "months": {}}
        
    stats = {"total": 0, "months": {}}
    
    # Get all month directories
    months = sorted(os.listdir(base_dir), reverse=True)
    
    for month in months:
        month_dir = os.path.join(base_dir, month)
        month_papers = []
        
        # Read all markdown files in the month directory
        for filename in os.listdir(month_dir):
            if not filename.endswith('.md'):
                continue
            
            # Read papers from this file
            month_papers.extend(read_existing_papers(month_dir))
        
        # Add month stats
        if month_papers:
            stats["months"][month] = len(month_papers)
            stats["total"] += len(month_papers)
            
    return stats
