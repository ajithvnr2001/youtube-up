#!/usr/bin/env python3.8

import argparse
import http.client
import http.client
import os
import random
import time
import glob, mimetypes

import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow


http.client.RETRIES = 1

MAX_RETRIES = 10

RETRIABLE_EXCEPTIONS = (http.client.HTTPException, IOError, http.client.NotConnected,
  http.client.IncompleteRead, http.client.ImproperConnectionState,
  http.client.CannotSendRequest, http.client.CannotSendHeader,
  http.client.ResponseNotReady, http.client.BadStatusLine)



RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

CLIENT_SECRETS_FILE = input('Enter your client credential secret file path:\n')

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

VALID_PRIVACY_STATUSES = ('public', 'private', 'unlisted')


# Authorize the request and store authorization credentials.
def get_authenticated_service():
    credentials = google.oauth2.credentials.Credentials.from_authorized_user_file(CLIENT_SECRETS_FILE, SCOPES)
    return build(API_SERVICE_NAME, API_VERSION, credentials=credentials)


def initialize_upload(youtube, options, MEDIA_FILE_PATH):
  tags = None
  if options.keywords:
    tags = options.keywords.split(',')

  body=dict(
    snippet=dict(
      title=options.title,
      description=options.description,
      tags=tags,
      categoryId=options.category
    ),
    status=dict(
      privacyStatus=options.privacyStatus
    )
  )

  insert_request = youtube.videos().insert(
    part=','.join(body.keys()),
    body=body,

    media_body=MediaFileUpload(MEDIA_FILE_PATH, chunksize=-1, resumable=True)
  )

  resumable_upload(insert_request)

def resumable_upload(request):
  response = None
  error = None
  retry = 0
  while response is None:
    try:
      print('Uploading file...')
      status, response = request.next_chunk()
      if response is not None:
        if 'id' in response:
          print('Video id "%s" was successfully uploaded.' % response['id'])
        else:
          exit('The upload failed with an unexpected response: %s' % response)
    except HttpError as e:
      if e.resp.status in RETRIABLE_STATUS_CODES:
        error = 'A retriable HTTP error %d occurred:\n%s' % (e.resp.status,
                                                             e.content)
      else:
        raise
    except RETRIABLE_EXCEPTIONS as e:
      error = 'A retriable error occurred: %s' % e

    if error is not None:
      print(error)
      retry += 1
      if retry > MAX_RETRIES:
        exit('No longer attempting to retry.')

      max_sleep = 2 ** retry
      sleep_seconds = random.random() * max_sleep
      print('Sleeping %f seconds and then retrying...' % sleep_seconds)
      time.sleep(sleep_seconds)

if __name__ == '__main__':
  youtube = get_authenticated_service()

  MEDIA_FOLDER_PATH = input('Enter VIDEOS FOLDER PATH you wish to upload:\n')
  for video_file in glob.glob(os.path.join(MEDIA_FOLDER_PATH, '*.*')):
    mimetypes.init()
    mimestart = mimetypes.guess_type(video_file)[0]
    if mimestart != None:
      mimestart = mimestart.split('/')[0]
      if mimestart == 'video':
        title = description = video_file.split('/')[-1]
        parser = argparse.ArgumentParser()
        parser.add_argument('--file', required=False, help='Video file to upload')
        parser.add_argument('--title', help='Video title', default=title)
        parser.add_argument('--description', help='Video description', default=description)
        parser.add_argument('--category', default='22', help='Numeric video category. ' + 'See https://developers.google.com/youtube/v3/docs/videoCategories/list')
        parser.add_argument('--keywords', help='Video keywords, comma separated', default='')
        parser.add_argument('--privacyStatus', choices=VALID_PRIVACY_STATUSES, default='private', help='Video privacy status.')
        args = parser.parse_args()
        try:
          initialize_upload(youtube, args, video_file)
        except HttpError as e:
          print('An HTTP error %d occurred:\n%s' % (e.resp.status, e.content))
