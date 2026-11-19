"""Independent read-only archive verifier. Exit 2 on an integrity failure."""
import argparse,json,sys
from pathlib import Path
from candle_archive import ArchiveError,verify_archive

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True)
    parser.add_argument('--pin-file',help='Optional independently retained prior head JSON')
    args=parser.parse_args()
    try:
        pin=json.loads(Path(args.pin_file).read_text(encoding='utf-8-sig')) if args.pin_file else None
        report=verify_archive(args.root,expected_head=pin)
    except (ArchiveError,OSError,ValueError,KeyError,TypeError) as error:
        # No raw candle/account/auth output.
        print(json.dumps({'verified':False,'error':str(error),'orders_enabled':False}))
        return 2
    print(json.dumps({**report,'orders_enabled':False},sort_keys=True))
    return 0
if __name__=='__main__':sys.exit(main())
