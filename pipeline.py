#!/usr/bin/env python3
"""
Master pipeline for updating Cantonese Lyrics Analysis Dashboard.

Steps:
1. Run analysis on the latest CSV data (produces .json files in data/)
2. Build the dashboard HTML/JS (produces docs/index.html and docs/data.js)
"""

import sys
import build_dashboard


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Update Cantonese Lyrics Dashboard')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        '--web-only',
        action='store_true',
        help='Skip analysis, only rebuild dashboard HTML',
    )
    mode.add_argument(
        '--lexical-only',
        action='store_true',
        help='Refresh word diversity/repetition using cached NLP results, then rebuild',
    )
    args = parser.parse_args()

    print('Starting pipeline...')

    # 1. Run Analysis
    if args.lexical_only:
        from refresh_lexical import refresh

        refresh()
    elif not args.web_only:
        print('\n>>> Step 1: Running Analysis (this may take a while)...')
        try:
            import run_analysis

            run_analysis.main()
        except Exception as e:
            print(f'Error in analysis step: {e}')
            sys.exit(1)
    else:
        print('\n>>> Step 1: Skipped (Web Only mode)')

    # 2. Build Dashboard
    print('\n>>> Step 2: Building Dashboard...')
    try:
        build_dashboard.run()
    except Exception as e:
        print(f'Error in build step: {e}')
        sys.exit(1)

    print('\nPipeline completed successfully!')
    print('Open docs/index.html to view the dashboard.')


if __name__ == '__main__':
    main()
