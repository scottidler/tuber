#!/bin/env python3

import os
import re
import sys
import json
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
    '''Sanitize the title to be used as a valid filename.'''
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        title = title.replace(char, '-')
    return title

def extract_video_id(youtube_url):
    '''Extracts the video ID from a YouTube URL.'''
    pattern = r'(youtu\.be\/|youtube\.com\/(watch\?(.*&)?v=|(embed|v)\/))([^?&"\>]+)'
    match = re.search(pattern, youtube_url)
    return match.group(5) if match else None

def get_video_metadata(api_key, youtube_url):
    '''Fetch metadata for a given YouTube video ID.'''

    video_id = extract_video_id(youtube_url)
    youtube = build('youtube', 'v3', developerKey=api_key)

    request = youtube.videos().list(
        part='snippet,contentDetails,statistics',
        id=video_id
    )
    response = request.execute()

    if not response['items']:
        return 'No video found for this ID.'

    snippet = response['items'][0]['snippet']
    return {
        'url': youtube_url,
        'title': snippet['title'],
        'description': snippet['description'],
        'channel': snippet['channelTitle'],
        'published': snippet.get('publishedAt'),
        'tags': sanitize_tags(snippet.get('tags', [])),
    }

def generate_embed_code(video_id, width, height):
    '''Generates the iframe embed code for a given video ID with specified width and height.'''
    return f'<iframe width="{width}" height="{height}" src="https://www.youtube.com/embed/{video_id}" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>'

def create_markdown_file(metadata, embed_code, config, vault_path):
    '''Creates a markdown file in the Obsidian vault for the given video metadata.'''
    youtube_folder_path = os.path.join(os.path.expanduser(vault_path), 'youtube')
    os.makedirs(youtube_folder_path, exist_ok=True)

    title = sanitize_filename(metadata['title'])
    file_name = f'{title}.md'
    file_path = os.path.join(youtube_folder_path, file_name)

    with open(file_path, 'w') as file:
        file.write('---\n')
        file.write(f'date: {datetime.now().strftime("%Y-%m-%d")}\n')
        file.write(f'day: {datetime.now().strftime("%a")}\n')
        file.write(f'time: {datetime.now().strftime("%H:%M")}\n')
        tags = metadata.get('tags', [])
        sanitized_tags = ['#' + tag for tag in sanitize_tags(tags)]
        file.write(f'tags: [{", ".join(sanitized_tags)}]\n')
        file.write(f'type: link\n')
        file.write(f'url: {metadata.get("url", "")}\n')
        file.write(f'author: {metadata.get("channel", "")}\n')
        file.write('---\n\n')

        file.write(f'# {metadata["title"]}\n\n')
        file.write(f'{embed_code}\n\n')
        file.write('## Description\n')
        file.write(f'{metadata["description"]}\n\n')

def epilog():
    max_key_length = max(len(key) for key in RESOLUTIONS.keys()) + 1
    return 'Available Resolutions:\n' + \
           '\n'.join([f'{key.ljust(max_key_length)}: {value[0]}x{value[1]}' for key, value in RESOLUTIONS.items()])

def main(args):
    if not TUBER_API_KEY:
        print('API key not found. Set the TUBER_API_KEY environment variable.', file=sys.stderr)
        sys.exit(1)

    metadata = get_video_metadata(TUBER_API_KEY, args.youtube_url)
    print(json.dumps(metadata, indent=4, sort_keys=True))

    width, height = RESOLUTIONS[args.resolution]
    embed_code = generate_embed_code(video_id, width, height)
    print('\nEmbed Code:')
    print(embed_code)

    create_markdown_file(metadata, embed_code, args.vault)

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

    config = {}
    if os.path.exists(config_file):
        with open(config_file, 'r') as file:
            yaml_content = YAML(typ='safe').load(file)
            if isinstance(yaml_content, dict):
                config = {k.replace('-', '_'): v for k, v in yaml_content.items()}
            else:
                print(f'Warning: YAML config file {config_file} is not valid yaml.', file=sys.stderr)

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
        metavar='RES',
        choices=RESOLUTIONS.keys(),
        help='Video resolution (default: %(default)s)')
    parser.add_argument(
        '--vault',
        metavar='PATH',
        help='Path to the Obsidian vault (default: %(default)s)')

    args = parser.parse_args(rem)
    main(args)

