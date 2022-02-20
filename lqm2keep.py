#!/usr/bin/env python
import argparse
import datetime
import json
import os
import gkeepapi
import keyring
import time
from zipfile import ZipFile

# --- Command-line args -------------------------------------------------------
parser = argparse.ArgumentParser(description='Args')
parser.add_argument('-u', required=True, help='Google Keep username')
parser.add_argument('-p', required=True, help='Google Keep password')
parser.add_argument('-d', help='*.lqm files directory (\'.\' by default)')
parser.add_argument('-o', help='output files directory (\'output\' by default)')
args = parser.parse_args()

gkeep_username = args.u
gkeep_password = args.p

source_directory = args.d
if not source_directory:
    source_directory = "."

output_directory = args.o
if not output_directory:
    output_directory = "output"
# -----------------------------------------------------------------------------

# --- Google Keep authentication ----------------------------------------------
keep = gkeepapi.Keep()
token = keyring.get_password('google-keep-token', gkeep_username)
if token:
    print('Google Keep: Auth with resume token...')
    keep.resume(gkeep_username, token)
else:
    print('Google Keep: Auth with username and password...')
    try:
        keep.login(gkeep_username, gkeep_password)
    except Exception:
        print('Google Keep: Auth failed. Set up app password within google account.')
        raise
    token = keep.getMasterToken()
    keyring.set_password('google-keep-token', gkeep_username, token)

print('Google Keep: Auth OK')
# -----------------------------------------------------------------------------

print('Processing notes...')

memo_ids = set()

for file in os.listdir(source_directory):
    if file.endswith('.lqm'):
        zip_file = ZipFile(source_directory + "/" + file, 'r')
        memo_json_file = zip_file.read('memoinfo.jlqm')
        memo_json = json.loads(memo_json_file)

        category_object = memo_json.get('Category')
        memo = memo_json.get('Memo')
        memo_object = memo_json.get('MemoObjectList')[0]

        # Memo properties
        memo_id = memo_object.get('MemoId')
        memo_plain_text = memo_object.get('DescRaw')
        memo_date = datetime.datetime.fromtimestamp(memo.get('CreatedTime') / 1000).date().isoformat()
        memo_image_name = memo.get('PreviewImage')
        category_name = category_object.get('CategoryName')

        # Don't upload potentially duplicated notes to Google Keep
        if memo_id in memo_ids:
            memo_id = "%s+" % memo_id
        else:
            if memo_plain_text and len(memo_plain_text) > 0:
                label = keep.findLabel(category_name)
                if not label:
                    label = keep.createLabel(category_name)

                note_title = "Заметка №%d от %s" % (memo_id, memo_date)

                keep.createNote(note_title, memo_plain_text).labels.add(label)

                # Google blocks too frequent api calls
                time.sleep(0.5)
                keep.sync()
            else:
                print("Skipping blank note #%s" % memo_id)

        memo_ids.add(memo_id)

        output_path = output_directory + "/%s/%s (%s)" % (category_name, str(memo_id), memo_date)

        # Extract image if exists
        if memo_image_name:
            zip_file.extract('images/' + memo_image_name, output_path)
        zip_file.close()

        # Write memo to text file
        if memo_plain_text:
            filename = output_path + "/plain_text.txt"
            os.makedirs(os.path.dirname(output_path + "/plain_text.txt"), exist_ok=True)
            with open(filename, "w", encoding="utf-8") as memo_text_file:
                memo_text_file.write(memo_plain_text)

print("Processed %d memos." % (len(memo_ids)))
