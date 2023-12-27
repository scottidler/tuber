#!/bin/env python3

import os
import re
import sys
import json
from datetime import datetime
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from googleapiclient.discovery import build
from ruamel.yaml import YAML

TUBER_API_KEY = os.getenv('TUBER_API_KEY')
RESOLUTIONS = {
    'nHD': (640, 360),
    'FWVGA': (854, 480),
    'qHD': (960, 540),
    'SD': (1280, 720),
    'WXGA': (1366, 768),
    'HD+': (1600, 900),
    'FHD': (1920, 1080),
    'WQHD': (2560, 1440),
    'QHD+': (3200, 1800),
    '4K UHD': (3840, 2160),
    '5K': (5120, 2880),
    '8K UHD': (7680, 4320),
    '16K UHD': (15360, 8640)
}

def load_config(config_path):
    yaml = YAML(typ='safe')
    try:
        with open(config_path) as file:
            return yaml.load(file)
    except FileNotFoundError:
        return {}

def sanitize_tags(tags):
    '''Sanitize tags for Obsidian: lowercase with hyphens instead of spaces or other characters.'''
    print(f'sanitize_tags: {tags}')
    def sanitize_tag(tag):
        tag = tag.replace("'", '')          # Remove apostrophes
        tag = re.sub(r"[^\w\s]", '-', tag)  # Replace non-alphanumeric characters with hyphens
        tag = tag.replace(' ', '-').lower() # Replace spaces with hyphens and lowercase
        return tag
    return [
        sanitize_tag(tag)
        for tag
        in tags
    ]

def sanitize_filename(title):
    ''' Sanitize the title to be used as a valid filename. '''
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        title = title.replace(char, '-')
    return title

def format_frontmatter(frontmatter_config, metadata):
    ''' Formats the frontmatter for the markdown file using the provided configuration and metadata. '''
    frontmatter = frontmatter_config.copy()
    frontmatter['date'] = datetime.now().strftime('%Y-%m-%d')
    frontmatter['day'] = datetime.now().strftime('%a')
    frontmatter['time'] = datetime.now().strftime('%H:%M')
    frontmatter['tags'] = sanitize_tags(metadata.get('tags', []))
    frontmatter['url'] = f'https://www.youtube.com/watch?v={metadata.get("id", "")}'
    frontmatter['author'] = metadata.get('channel', '')

    frontmatter_str = '---\n'
    for key, value in frontmatter.items():
        if key == 'tags':
            frontmatter_str += f'{key}:\n'
            for tag in value:
                frontmatter_str += f'  - {tag}\n'
        else:
            frontmatter_str += f'{key}: {value}\n'
    frontmatter_str += '---\n\n'

    return frontmatter_str

def extract_video_id(youtube_url):
    ''' Extracts the video ID from a YouTube URL. '''
    pattern = r'(youtu\.be\/|youtube\.com\/(watch\?(.*&)?v=|(embed|v)\/))([^?&"\'>]+)'
    match = re.search(pattern, youtube_url)
    return match.group(5) if match else None

def get_video_metadata(api_key, video_id):
    ''' Fetch metadata for a given YouTube video ID. '''
    youtube = build('youtube', 'v3', developerKey=api_key)

    request = youtube.videos().list(
        part='snippet,contentDetails,statistics',
        id=video_id
    )
    response = request.execute()

    if not response['items']:
        return 'No video found for this ID.'

    snippet = response['items'][0]['snippet']
    metadata = {
        'id': video_id,
        'title': snippet['title'],
        'description': snippet['description'],
        'channel': snippet['channelTitle'],
        'published': snippet.get('publishedAt'),
        'tags': snippet.get('tags', []),
    }
    print(f"get_video_metadata - tags: {metadata['tags']}, type: {type(metadata['tags'])}")
    return metadata

def generate_embed_code(video_id, width, height):
    '''Generates the iframe embed code for a given video ID with specified width and height.'''
    return f'<iframe width="{width}" height="{height}" src="https://www.youtube.com/embed/{video_id}" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>'

def create_markdown_file(metadata, embed_code, vault_path, frontmatter_config):
    ''' Creates a markdown file in the Obsidian vault for the given video metadata. '''
    title = sanitize_filename(metadata['title'])
    file_name = f"{title}.md"
    youtube_folder_path = os.path.join(os.path.expanduser(vault_path), 'youtube')
    os.makedirs(youtube_folder_path, exist_ok=True)
    file_path = os.path.join(youtube_folder_path, file_name)

    frontmatter_str = format_frontmatter(frontmatter_config, metadata)

    with open(file_path, 'w') as file:
        file.write(frontmatter_str)
        file.write(embed_code)
        file.write('\n\n## Description\n')
        file.write(metadata['description'])

def main(args):
    if not TUBER_API_KEY:
        print('API key not found. Set the TUBER_API_KEY environment variable.', file=sys.stderr)
        sys.exit(1)

    video_id = extract_video_id(args.youtube_url)
    if not video_id:
        print('Invalid YouTube URL.', file=sys.stderr)
        return

    metadata = get_video_metadata(TUBER_API_KEY, video_id)
    frontmatter_config = args.frontmatter if 'frontmatter' in args else {}
    create_markdown_file(metadata, generate_embed_code(video_id, *RESOLUTIONS[args.resolution]), args.vault, frontmatter_config)


if __name__ == '__main__':
    parser = ArgumentParser(
        description='Fetch YouTube video metadata and generate embed code.',
        formatter_class=RawDescriptionHelpFormatter,
        add_help=False)
    parser.add_argument(
        '--config',
        metavar='PATH',
        default='~/.config/tuber/tuber.yml',
        help='default="%(default)s"; config filepath')

    ns, rem = parser.parse_known_args(sys.argv[1:])
    config_file = os.path.expanduser(ns.config)

    config = load_config(config_file)

    parser = ArgumentParser(
        parents=[parser],
        formatter_class=RawDescriptionHelpFormatter)
    parser.set_defaults(**config)
    parser.add_argument(
        'youtube_url',
        metavar='youtube-url',
        help='YouTube video URL')
    parser.add_argument(
        '-r', '--resolution',
        metavar='RESOLUTION',
        choices=RESOLUTIONS.keys(),
        help='Video resolution (default: %(default)s)')
    parser.add_argument(
        '--vault',
        metavar='PATH',
        help='Path to the Obsidian vault (default: %(default)s)')

    args = parser.parse_args(rem)
    main(args)

