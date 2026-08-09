# Morian deployment ve kabul kontrolü

## Yerel

```powershell
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

`.env` içindeki `SEC_USER_AGENT` gerçek iletişim e-postası içermelidir.

## Docker Compose

```powershell
Copy-Item .env.example .env
docker compose up --build -d
```

Servisler: API `:8000`, n8n `:5678`, Qdrant `:6333`. İlk açılışta n8n owner hesabını oluşturun, `n8n/*.json` dosyalarını içe aktarın ve Google Drive/Qdrant/embedding/chat credentials seçin. Workflow'ları test ettikten sonra aktive edin.

Public domain kullanırken `.env` içinde `APP_ENV=production`, `ALLOWED_HOSTS=alanadiniz.com` ve `CORS_ORIGINS=https://alanadiniz.com` ayarlanmalıdır. Reverse proxy TLS/HTTPS sağlamalıdır. Varsayılan PostgreSQL ve n8n encryption değerlerini üretimde mutlaka benzersiz güçlü secret'larla değiştirin.

## Kabul kontrolü

1. `GET /api/health` → `ok`.
2. `GET /api/ready` → database ve statik dosya kontrolü başarılı.
3. Dashboard'da 2–4 ticker karşılaştırması sonuçlanır.
4. NASDAQ-100 taraması job kimliği üretir ve progress ilerler.
5. Şirket detayında TTM/data-quality ve grafikler görünür.
6. CSV export indirilir.
7. `GET /api/filings/MSFT` resmi filing listesi döndürür.
8. Ingestion workflow aktifken `POST /api/filings/MSFT/ingest?limit=1` Qdrant collection yazar.
9. Sayısal soru `structured`, risk/metin sorusu `filing_rag` rotasına gider.
10. `LLM_PROVIDER=none` durumunda temel analiz çalışır; arayüz AI düğmesini pasif gösterir.

## Operasyon notları

- SQLite tek makine kurulumu içindir. Çoklu API replica hedefinde finans tabloları/job deposu PostgreSQL adaptörüne taşınmalıdır.
- Redis ve PostgreSQL Compose içinde n8n queue/kalıcılığı için hazırdır.
- SEC ve Yahoo cache volume içinde korunur.
- Backup hedefleri: `stock_data`, `postgres_data`, `qdrant_data`, `n8n_data` volume'ları.
