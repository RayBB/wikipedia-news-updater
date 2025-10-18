"""
# This is a script that will collect changes from Wikipedia pages and output them to a JSON files.

# Start time (optional)
# End time (optional)
# Min time between revisions (optional)
# Note that it will ignore min time for the most recent revision.

# Max diffs

URL to get the diff:
https://en.wikipedia.org/w/api.php?action=compare&fromrev=1293623480&torev=1317452177&format=json&formatversion=2


URL To get the diff ids:
https://en.wikipedia.org/w/api.php?action=query&prop=revisions&titles=No_Kings_protests_(October_2025)&rvlimit=500&rvprop=ids|timestamp|user|comment|flags&format=json&formatversion=2

"""

import httpx
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Extract the title from the API URL
title = "No_Kings_protests_(October_2025)"
title = "California_Senate_Bill_79"

def get_revision_list(title, limit=500):
    """
    Get a list of revisions for a given Wikipedia page.
    """
    response = httpx.get(
        f"https://en.wikipedia.org/w/api.php?action=query&prop=revisions&titles={title}&rvlimit={limit}&rvprop=ids|timestamp|user|comment|flags&format=json&formatversion=2",
        headers={"User-Agent": "Wikipedia News Updater (https://github.com/RayBB/wikipedia-news-updater)"},
    )
    return response.json()


def process_revisions(json_data):
    """
    Process Wikipedia revision data to find pairs of revisions with at least one hour between them.

    Args:
        json_data: JSON data containing revision information

    Returns:
        List of dictionaries with revision pairs and timestamps
    """
    # Extract revisions from the JSON
    revisions = json_data["query"]["pages"][0]["revisions"]

    # Result list to store the pairs
    result = []

    # Start with the most recent revision (index 0)
    current_index = 0

    # Continue until we've processed all revisions
    while current_index < len(revisions):
        current_rev = revisions[current_index]
        current_timestamp = datetime.fromisoformat(
            current_rev["timestamp"].replace("Z", "+00:00")
        )

        # Find the next revision that's at least one hour away
        next_index = current_index + 1
        found = False

        while next_index < len(revisions):
            next_rev = revisions[next_index]
            next_timestamp = datetime.fromisoformat(
                next_rev["timestamp"].replace("Z", "+00:00")
            )

            # Check if the time difference is at least one hour
            if current_timestamp - next_timestamp >= timedelta(hours=1):
                # Add this pair to the result
                result.append(
                    {
                        "fromrev": next_rev["revid"],
                        "torev": current_rev["revid"],
                        "torev_timestamp": current_rev["timestamp"],
                    }
                )
                # Continue from the revision we found
                current_index = next_index
                found = True
                break

            next_index += 1

        # If we couldn't find a revision at least an hour away, we're done
        if not found:
            break

    return result


revision_list = get_revision_list(title)
revisions = process_revisions(revision_list)

revisions_count = len(revisions)
print(f"Found {revisions_count} revisions with at least one hour between them.")


def get_diff(fromrev, torev):
    response = httpx.get(
        f"https://en.wikipedia.org/w/api.php?action=compare&fromrev={fromrev}&torev={torev}&format=json&formatversion=2",
        headers={"User-Agent": "Wikipedia News Updater (https://github.com/RayBB/wikipedia-news-updater)"},
    )
    return response.json()["compare"]["body"]


def add_diff_to_revision(revision):
    new_revision = revision.copy()
    diff = get_diff(new_revision["fromrev"], new_revision["torev"])
    new_revision["diff"] = diff
    return new_revision


# Create a new array with the diffs
diff_limit = 10
new_revisions = []
for i, revision in enumerate(revisions):
    if i >= diff_limit:
        break
    new_revision = add_diff_to_revision(revision)
    new_revisions.append(new_revision)

# Write the new array to a JSON file
import os
import pathlib

def write_output_to_file(data, title):
    current_dir = pathlib.Path(__file__).parent.absolute()
    data_dir = os.path.join(current_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    output_file = os.path.join(data_dir, f"{title}.json")

    with open(output_file, "w") as f:
        json.dump(data, f, indent=4)

    print(f"Wrote revisions with diffs to {output_file}")

from openai import OpenAI
import time


# Read prompt.md as text
with open("prompt.md", "r") as f:
    prompt_text = f.read()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

def get_change_summary(diff):
    start_time = time.time()
    completion = client.chat.completions.create(
        extra_headers={
            "HTTP-Referer": "https://github.com/RayBB/wikipedia-news-updater",
            "X-Title": "Wikipedia News Updater",
        },
        model="mistralai/mistral-small-3.2-24b-instruct:free",
        # model="z-ai/glm-4.5-air:free",
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "ChangeSummary",
                "schema": {
                    "type": "object",
                    "properties": {
                        "importance": {
                            "type": "string",
                            "enum": ["HIGH", "MEDIUM", "LOW", "TRIVIAL"]
                        },
                        "reason": {"type": "string"},
                        "summary": {"type": "string"}
                    },
                    "required": ["importance", "reason", "summary"],
                    "additionalProperties": False
                }
            }
        },
        messages=[
            {"role": "system", "content": prompt_text},
            {"role": "user", "content": diff},
        ],
    )
    end_time = time.time()
    print(f"Response time: {end_time - start_time} seconds")

    print(completion.choices[0].message.content)

    return json.loads(completion.choices[0].message.content)

for revision in new_revisions:
    if "diff" not in revision:
        continue
    summary = get_change_summary(revision["diff"])
    revision["summary"] = summary

output = {
    "page": title,
    "last_checked": datetime.now().isoformat(),
    "changes": new_revisions
}

write_output_to_file(output, title)
