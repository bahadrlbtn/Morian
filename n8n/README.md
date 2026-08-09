# n8n içe aktarma

1. Beş JSON dosyasını n8n'de **Import from File** ile içe aktarın.
2. `STOCK_API_URL` ortam değişkenini ayarlayın (Docker'da genellikle `http://api:8000`).
3. Google Drive, Qdrant ve embedding credential'larını ilgili düğümlerde seçin.
4. Filing ingestion girdisinde `file_id`, `ticker`, `company`, `filing_type`, `filing_date`, `fiscal_year`, `source` alanlarını sağlayın.
5. Önce test execution çalıştırın; sonra webhook'u aktive edin.

`sec-filing-auto-ingestion.json` ve `filing-rag-query.json`, backend'in `/api/filings/{ticker}/ingest` ve `/api/query` uçları için gereken webhook yollarını sağlar.

Mevcut export kök dizinde değiştirilmeden bırakılmıştır. Yeni orkestratör sayısal sorguları backend'e gönderir. Belge soruları için mevcut Retrieval QA hattı kullanılabilir; prompt'a “yalnızca retrieved context, sayı üretme” kuralı eklenmelidir.
