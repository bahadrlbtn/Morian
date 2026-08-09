# Morian · AI Equity Intelligence

ABD hisseleri için SEC verisini esas alan, finansal metrikleri deterministik hesaplayan ve n8n/Qdrant RAG hattını koruyan yapay zekâ destekli araştırma platformu.

## Hızlı başlangıç

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --reload
```

Arayüz: `http://127.0.0.1:8000` — API dokümanı: `http://127.0.0.1:8000/docs`

SEC, otomatik isteklerde iletişim bilgisi içeren bir User-Agent ister. `.env` içindeki `SEC_USER_AGENT` değerini gerçek e-posta adresinizle değiştirin.

## İlkeler

- Finansal rakamlar ve puanlar yalnızca Python fonksiyonlarıyla hesaplanır.
- Eksik değerler `null` kalır; sıfıra çevrilmez ve puanları yapay biçimde artırmaz.
- Her alan kaynak, dönem, filing tarihi ve güncelleme zamanıyla izlenebilir.
- Qdrant yalnızca 10-K/10-Q/rapor metinleri içindir.
- LLM, sadece hesaplanmış JSON'u yorumlar; sayısal gerçeklerin kaynağı değildir.
- Watchlist'ler SQLite içinde saklanır; detay ekranı tarihsel revenue/FCF ve margin grafiklerini gösterir.
- Morian Score Lab ile kategori ve alt metrik ağırlıkları şirket bazında değiştirilebilir; “neden değerlendirilmeli / neden elenmeli” gerekçeleri deterministik kanıtlardan üretilir.

AI yorumunu kullanmak istemiyorsanız `LLM_PROVIDER=none` bırakın. OpenAI için `LLM_PROVIDER=openai` ve `OPENAI_API_KEY`; tamamen yerel kullanım için `LLM_PROVIDER=ollama` ve çalışan bir Ollama sunucusu ayarlayın.

Detaylı mimari ve geçiş planı için [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), API örnekleri için [docs/API.md](docs/API.md) dosyasına bakın.

Tamamlanma durumu [docs/ROADMAP.md](docs/ROADMAP.md), Docker ve kabul adımları [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) içindedir.

## Test

```powershell
python -m unittest discover -s tests -v
```

Scoring/normalizasyon kuralları değiştiğinde cache'teki SEC verilerini kullanarak mevcut şirketleri yeniden hesaplamak için:

```powershell
.\.venv\Scripts\python.exe -m scripts.rebuild_scores
```

Kategori kapsamı `%40` altındaysa o kategori, ağırlıklı toplam veri kapsamı `%60` altındaysa Final Score `null` bırakılır. Bu şirketler sıralamaya dahil edilmez; eksik veri yüksek puana dönüşmez.
