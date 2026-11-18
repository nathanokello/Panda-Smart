# Data sources for weather, soil, crops and languages

Checked on 18 November 2026. Licences and access change: check again before
you depend on any source, and before anything commercial. "Built" means there
is code in this repo; everything else is a plan.

## The key point: free is often non-commercial only

Panda Smart plans to charge cooperatives, SACCOs and buyers a subscription, so
it is a commercial product. Several "free" sources only allow non-commercial use:

| Source | Free for a commercial product? |
|---|---|
| NASA POWER | Yes: open data, no key |
| Open-Meteo hosted API | **No.** Free tier is non-commercial only (under 10,000 calls/day). Needs a paid plan or a self-hosted server |
| NLLB-200 translation models | **No.** Model licence is CC BY-NC 4.0 (non-commercial) |
| SoilGrids data | Yes (CC BY 4.0), but its REST API is currently paused (see below) |

A hackathon demo or university research use is fine on the free tiers.

## 1. Weather

| Source | Access | Status in Panda Smart |
|---|---|---|
| **NASA POWER** | Free, no key, daily data since 1981, roughly 55 km grid | **Built:** `python manage.py fetch_rainfall` stores daily rainfall per ward; planting advice uses it |
| **Open-Meteo** | Free, no key, non-commercial only; data CC BY 4.0 (attribution required) | **Built, off by default:** `OPEN_METEO_ENABLED=1` shows a 7-day forecast on the farmer dashboard, cached 1 hour per ward |
| CHIRPS | Satellite rainfall since 1981; good for rainfall onset | Demo CSV and `import_rainfall` command exist; no automatic download |
| ERA5 (Copernicus) | Free historical reanalysis, needs an account | Planned |
| Kenya Meteorological Department | Official seasonal forecasts | Cross-check by hand; no API used |
| Large AI weather models (Prithvi-WxC, Aurora) | Heavy to run | Not planned. A small model on CHIRPS and NASA POWER data for one county is more realistic |

NASA POWER's 55 km grid is coarse: one value covers many wards. Treat it as
"rain in this area", not "rain on this farm".

## 2. Soil

| Source | Access | Notes |
|---|---|---|
| **iSDAsoil** | About 30 m, Africa-wide (pH, nitrogen, carbon, texture…). The API **needs an account**: log in with username and password to get a short-lived token. The data is also published as an open AWS bucket | Planned. Next step: register, confirm the parameter names in iSDA's docs, then add a `soil_lookup` command like `fetch_rainfall` |
| SoilGrids (ISRIC) | 250 m, CC BY 4.0 | ISRIC's documentation says the REST API is **temporarily paused**, and the v2.0 API was always marked beta. Do not rely on it as a fallback; download the data instead if needed |
| KALRO / Kenya soil survey | Best local accuracy | Request access |
| Farmer's own soil test | Most accurate for that farm | Planned: let farmers enter results |

Suggested flow (planned): coordinates → soil values → simple rules (for example
low pH → liming advice) → plain-language explanation → "see an extension officer".

## 3. Crops

| Source | Use | Notes |
|---|---|---|
| FAO EcoCrop | Each crop's temperature, rainfall and pH range | Planned: transparent crop matching, no training needed |
| CABI PlantwisePlus, KALRO publications | Reviewed advice text | Planned knowledge base; check reuse terms |
| PlantVillage, PlantDoc (Kaggle, Hugging Face) | Plant-disease images | Models trained on these do poorly on real field photos. Collect local labelled photos with extension officers first |
| Kaggle "crop recommendation" datasets | — | Mostly from India; not evidence for Kenya |

## 4. Languages

| Resource | Notes |
|---|---|
| `Helsinki-NLP/opus-mt-en-sw`, `opus-mt-sw-en` | English ↔ Kiswahili translation; check each model card's licence |
| Meta NLLB-200 (`facebook/nllb-200-distilled-600M`) | Covers Kamba (`kam_Latn`) and Kikuyu (`kik_Latn`). **Licence CC BY-NC 4.0: non-commercial only.** Quality is lower for these languages; native speakers must check output |
| Whisper (Swahili fine-tunes), Meta MMS (ASR, `mms-tts-swh`), Common Voice Swahili | Speech in and out. Check each licence |
| Masakhane, Lelapa InkubaLM | African-language community resources |

Voice is used for input and output only, never to identify a person (Kenya
Data Protection Act, 2019).

## How the pieces fit (target design)

1. Farmer picks a ward (built) or, later, speaks a question (planned).
2. Weather (built: NASA POWER rainfall, Open-Meteo forecast) and soil (planned) for that place.
3. Rules match crops and timing (built for timing; crop matching planned).
4. A language model rewrites the result in plain words (planned). The numbers
   always come from the rules, never from the model.
5. Translation to Kiswahili or Kikamba (planned; licence above).

Start with one county and one crop, for example Machakos and maize, and check
the advice with real farmers and extension officers before claiming accuracy.

## Sources checked

- Open-Meteo terms: https://open-meteo.com/en/terms
- NASA POWER daily API: https://power.larc.nasa.gov/docs/services/api/temporal/daily/
- SoilGrids status: https://docs.isric.org/globaldata/soilgrids/ and https://rest.isric.org/
- iSDAsoil API (login flow): https://jentic.com/apis/isdasoil (third-party description of iSDA's API; confirm with iSDA)
- NLLB-200 model card and language list: https://huggingface.co/facebook/nllb-200-distilled-600M
