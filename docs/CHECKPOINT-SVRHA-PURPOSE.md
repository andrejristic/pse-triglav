# CHECKPOINT.PY: SVRHA / PURPOSE

*19. oktobar 2026 / 19 October 2026.*

**Fajl / The file:** [triglav/shell/adapters/checkpoint.py](../triglav/shell/adapters/checkpoint.py)

Link je relativan: na Andrejevom računaru, u kopiji `zeravatechnologies` i u kopiji `andrejristic` vodi na `checkpoint.py` te iste kopije. / The link is relative: on Andrej's computer, in the `zeravatechnologies` copy and in the `andrejristic` copy it leads to `checkpoint.py` in that same copy.

---

## Srpski

**Šta je to.** `checkpoint.py` je zajednički kontrolni punkt za buduće adaptere Triglava (MCP, OpenAI-kompatibilni API, A2A). On sam nije adapter. Ima dvije radnje:

- **ulaz (`inbound`):** ono što stiže našem agentu propušta samo kao bukvalan tekst, a sve skriveno ide u SHARED_LIB;
- **izlaz (`outbound`):** ono što naš agent šalje van zaustavlja ako je korak ka zlu, curenje, ili ako je agent van rada.

Jedna razmjena je jedan korak: na kraju svake radnje SHARED_LIB zaključi, pa se štetan korak zaustavi **prije** nego što ode van. Radi preko Triglavove sabirnice (`BusChannel`), sa istim pravilima kao i sve ostalo.

**Zašto postoji.** Napisan je 18. oktobra, kao prvi dio rada na adapterima. Dok su se pisali sami adapteri, sigurnosni filter je zaustavio Claudeov odgovor; ovaj fajl je tada već bio zapisan i nije bio zaustavljen. Adaptere sada piše Dhiraj Sah (plan granta, mjeseci 1–3), i oni treba da koriste ovaj fajl kao osnovu.

**Distribucija.** `checkpoint.py` je samo patrljak onoga što će narasti kad dođu adapteri. Postoji u sve tri kopije repoa, ali **ne ide u javnu distribuciju** (.deb, .exe, pip paket) dok adapteri ne postoje: `packaging/build_deb.sh`, `.github/workflows/build.yml` i `pyproject.toml` ga izostavljaju.

**Stanje.** Fajl je nepromijenjen od 18. oktobra. Ništa ga još ne koristi i nema svoje testove; testovi dolaze s adapterima. Odluka o adapterima je u repou sajta: `grantovi/5-foresight/ODLUKA-O-ADAPTERIMA.md` i `DECISION-ON-ADAPTERS.md`.

## English

**What it is.** `checkpoint.py` is the shared checkpoint for Triglav's future adapters (MCP, an OpenAI-compatible API, A2A). It is not an adapter itself. It has two operations:

- **inbound:** what reaches our agent goes through only as literal text; anything hidden goes to SHARED_LIB;
- **outbound:** what our agent sends out is stopped if it is a step toward harm, a leak, or if the agent is out of work.

One exchange is one step: each operation ends with SHARED_LIB concluding, so a harmful step is stopped **before** it leaves. It works over Triglav's bus (`BusChannel`), with the same rules as everything else.

**Why it exists.** It was written on 18 October as the first part of the work on the adapters. While the adapters themselves were being written, a safety filter stopped Claude's response; this file had already been written and was not stopped. Dhiraj Sah now writes the adapters (grant plan, months 1-3), and they are meant to build on this file.

**Distribution.** `checkpoint.py` is only a stub of what will grow when the adapters come. It exists in all three copies of the repository but **does not go into public distribution** (.deb, .exe, pip package) until the adapters exist: `packaging/build_deb.sh`, `.github/workflows/build.yml` and `pyproject.toml` leave it out.

**Status.** The file is unchanged since 18 October. Nothing uses it yet and it has no tests of its own; the tests come with the adapters. The decision on the adapters is in the site repository: `grantovi/5-foresight/DECISION-ON-ADAPTERS.md` and `ODLUKA-O-ADAPTERIMA.md`.
