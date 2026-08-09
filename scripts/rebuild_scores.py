from __future__ import annotations

from app.services import AnalysisService


def main() -> None:
    service=AnalysisService()
    with service.db.connect() as con:
        tickers=[row[0] for row in con.execute("SELECT ticker FROM companies ORDER BY ticker")]
    failures=[]
    for index,ticker in enumerate(tickers,1):
        try: service.analyze(ticker)
        except Exception as exc: failures.append((ticker,str(exc)))
        if index%10==0 or index==len(tickers): print(f"rescored {index}/{len(tickers)}",flush=True)
    print(f"complete={len(tickers)-len(failures)} failed={len(failures)}")
    for ticker,error in failures: print(f"FAILED {ticker}: {error}")


if __name__=="__main__": main()
