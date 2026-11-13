import argparse
from pathlib import Path
from .db import connect
from .pipeline import ingest_drop
from .reporting import generate_reports
def main():
 p=argparse.ArgumentParser(description="Agentic Universe Assignment A pipeline");s=p.add_subparsers(dest="cmd",required=True);s.add_parser("init");i=s.add_parser("ingest");i.add_argument("drop",type=Path);r=s.add_parser("report");r.add_argument("--out",type=Path,required=True);a=p.parse_args()
 if a.cmd=="init":c=connect();c.close();print("Database initialised")
 elif a.cmd=="ingest":print(ingest_drop(a.drop))
 else:print(generate_reports(a.out))
if __name__=="__main__":main()
