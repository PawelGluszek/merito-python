# Duplicate File Finder

Narzędzie CLI do wyszukiwania zduplikowanych plików w drzewie katalogów. Rekurencyjnie przegląda katalogi, filtruje pliki po nazwie i rozmiarze, oblicza skróty SHA-256 i raportuje duplikaty.

**Autorzy:** Pawel Gluszek, Piotr Klebaniuk, Łukasz Banaś  
**Python:** 3.12+  
**Temat:** Wyszukiwarka zduplikowanych plików (temat 2)

## Opis działania

1. **Skanowanie** — rekurencyjne przejście drzewa katalogów generatorem (`yield from` + `os.scandir`), z leniwym filtrowaniem po rozmiarze i wzorcach glob.
2. **Pre-filtrowanie** — grupowanie plików po rozmiarze. Tylko pliki o identycznym rozmiarze mogą być duplikatami.
3. **Haszowanie** — obliczanie SHA-256 kandydatów. Plik czytany jest blokami przez własny iterator (`ChunkReader`). Haszowanie odbywa się współbieżnie (wątki `ThreadPoolExecutor`) lub równolegle (procesy `ProcessPoolExecutor`).
4. **Raportowanie** — grupowanie po identycznym hashu i wyświetlenie raportu z informacją o zmarnowanej przestrzeni dyskowej.

## Instrukcja uruchomienia

```bash
# Klonowanie repozytorium
git clone <url_repozytorium>
cd merito-python

# Utworzenie środowiska wirtualnego
python3 -m venv venv
source venv/bin/activate    # Linux/macOS
# venv\Scripts\activate     # Windows

# Instalacja zależności
pip install -r requirements.txt

# Generowanie danych testowych
python -m data.generate_test_data --output test_data --count 100

# Uruchomienie wyszukiwarki duplikatów
python main.py test_data

# Uruchomienie z filtrami
python main.py test_data --pattern "*.txt" "*.csv" --min-size 1KB

# Tryb procesów (zamiast wątków)
python main.py test_data --use-processes

# Uruchomienie benchmarku GIL
python main.py --benchmark test_data

# Uruchomienie testów
python -m pytest tests/ -v
```

### Opcje CLI

| Opcja | Opis |
|---|---|
| `directory` | Katalog do skanowania (domyślnie: `.`) |
| `--pattern`, `-p` | Wzorce glob, np. `"*.jpg" "*.png"` |
| `--min-size` | Minimalny rozmiar pliku (np. `1KB`, `10MB`) |
| `--max-size` | Maksymalny rozmiar pliku |
| `--algorithm`, `-a` | Algorytm haszowania: `md5`, `sha1`, `sha256`, `sha512` |
| `--workers`, `-w` | Liczba wątków/procesów roboczych |
| `--use-processes` | Użyj procesów zamiast wątków |
| `--benchmark` | Uruchom benchmark GIL |
| `--verbose`, `-v` | Zwiększ szczegółowość logów (`-v` INFO, `-vv` DEBUG) |

## Tabela mapowania zagadnień

| Zagadnienie | Gdzie w kodzie |
|---|---|
| Dekorator `measure_time` | `utils/decorators.py` → `measure_time(func)` |
| Dekorator z parametrami `retry` | `utils/decorators.py` → `retry(attempts, delay, exceptions)` |
| Dekorator `log_call` | `utils/decorators.py` → `log_call(func)` |
| Dekorator metody (korzysta z `self`) | `core/scanner.py` → `requires_config(method)` |
| `@property` z setterem | `core/scanner.py` → `FileScanner.min_size`, `FileScanner.max_size` |
| `@classmethod` | `core/scanner.py` → `FileScanner.with_size_range()` |
| `@staticmethod` | `core/scanner.py` → `FileScanner.human_readable_size()` |
| Iterator (`__iter__` + `__next__`) | `core/scanner.py` → klasa `ChunkReader` |
| Generator (`yield`) | `core/scanner.py` → `walk_files()` |
| `yield from` | `core/scanner.py` → `walk_files()` (rekurencyjna delegacja) |
| Wyrażenia generujące | `core/scanner.py` → `FileScanner.scan()` (leniwe filtrowanie) |
| Regex — grupy nazwane | `core/patterns.py` → `FILE_PATTERN`, `SIZE_PATTERN` |
| Regex — walidacja | `core/patterns.py` → `parse_size()`, `build_glob_filter()` |
| Regex — `re.VERBOSE` | `core/patterns.py` → wszystkie skompilowane wzorce |
| Wątki (`ThreadPoolExecutor`) | `core/hasher.py` → `hash_files_threaded()` |
| Synchronizacja (`Lock`) | `core/hasher.py` → `hash_files_threaded()` — ochrona słownika wyników |
| Procesy (`ProcessPoolExecutor`) | `core/analyzer.py` → `hash_files_multiprocess()` |
| Pomiar GIL | `benchmarks/gil_benchmark.py` → `run_benchmark()` |
| Testy (`pytest`) | `tests/` → 63 testy jednostkowe |
| CLI (`argparse`) | `main.py` → `parse_args()` |
| Logowanie (`logging`) | `utils/decorators.py`, `core/scanner.py`, `core/hasher.py` |

## Wyniki pomiarów wydajności

Środowisko testowe: Python 3.14.4 (CPython, GIL włączony), macOS, Apple Silicon, 8 rdzeni CPU.

### Benchmark 1: Czyste obliczenia CPU (suma kwadratów)

Zadanie: 8 × `sum_of_squares(2_000_000)` — czysto obliczeniowe, bez I/O.

| Metoda | Czas (s) | Przyspieszenie |
|---|---|---|
| Sekwencyjnie | 0.538 | 1.00x |
| 8 wątków | 0.549 | 0.98x |
| 8 procesów | 0.281 | 1.92x |

### Benchmark 2: Haszowanie plików SHA-256

Zadanie: 111 plików, łącznie 27.2 MB — operacja mieszana (I/O + CPU).

| Metoda | Czas (s) | Przyspieszenie |
|---|---|---|
| Sekwencyjnie | 0.023 | 1.00x |
| 8 wątków | 0.026 | 0.88x |
| 8 procesów | 0.128 | 0.18x |

## Wnioski dotyczące GIL

1. **GIL blokuje równoległość wątków dla kodu CPU-bound.** W benchmarku 1 (czyste obliczenia w Pythonie) 8 wątków nie dało żadnego przyspieszenia (0.98x) — wręcz minimalnie wolniej z powodu narzutu przełączania kontekstu. GIL pozwala w danej chwili na wykonanie kodu bajtowego Pythona tylko jednemu wątkowi.

2. **Procesy omijają GIL.** Każdy proces ma własny interpreter i własny GIL, dzięki czemu obliczenia mogą rzeczywiście przebiegać równolegle na wielu rdzeniach. W benchmarku 1 uzyskano przyspieszenie 1.92x na 8 rdzeniach (mniej niż liniowe ze względu na koszt tworzenia procesów i serializacji pickle).

3. **Dla małych plików narzut procesów dominuje.** W benchmarku 2 (27 MB danych) procesy były wielokrotnie wolniejsze niż sekwencja, ponieważ czas tworzenia puli procesów i serializacji argumentów przewyższył zysk z równoległości. Wątki także nie pomogły — pliki były zbyt małe, by I/O stanowiło wąskie gardło.

4. **Wątki pomagają przy dużym I/O.** Dla dużych plików (setki MB) wątki potrafią przyspieszyć haszowanie, ponieważ (a) operacje odczytu z dysku zwalniają GIL w oczekiwaniu na system operacyjny, (b) biblioteka `hashlib` zwalnia GIL podczas obliczania skrótu na dużych blokach danych (implementacja w C).

5. **Reguła praktyczna:** zadania I/O-bound → wątki lub `asyncio`; zadania CPU-bound w czystym Pythonie → procesy; obliczenia w rozszerzeniach C zwalniających GIL (NumPy, hashlib) → wątki mogą wystarczyć. Od Pythona 3.13t/3.14t dostępna jest eksperymentalna kompilacja bez GIL (free-threading), w której wątki mogą przyspieszać również obliczenia CPU.

## Struktura projektu

```
merito-python/
├── main.py                        # Punkt wejścia CLI (argparse)
├── requirements.txt               # Zależności (pytest)
├── README.md                      # Dokumentacja projektu
├── core/
│   ├── __init__.py
│   ├── scanner.py                 # Iterator, generator, dekoratory metod
│   ├── patterns.py                # Wyrażenia regularne
│   ├── hasher.py                  # Haszowanie plików (wątki)
│   └── analyzer.py                # Analiza duplikatów (procesy)
├── utils/
│   ├── __init__.py
│   └── decorators.py              # Dekoratory funkcji
├── benchmarks/
│   ├── __init__.py
│   └── gil_benchmark.py           # Benchmark GIL
├── data/
│   └── generate_test_data.py      # Generator danych testowych
└── tests/
    ├── __init__.py
    ├── test_decorators.py
    ├── test_scanner.py
    ├── test_patterns.py
    ├── test_hasher.py
    └── test_analyzer.py
```

## Napotkane problemy

1. **Narzut procesów dla małych danych.** Tworzenie puli procesów i serializacja argumentów przez `pickle` okazały się kosztowniejsze niż samo haszowanie plików o rozmiarze kilkuset KB. Rozwiązanie: pre-filtrowanie po rozmiarze pliku i używanie procesów dopiero dla dużych zbiorów danych.

2. **Deskryptor w dekoratorze-klasie.** Dekorator zaimplementowany jako klasa (z `__call__`) nie działa poprawnie jako dekorator metody bez implementacji protokołu deskryptora (`__get__`). Rozwiązanie: dla dekoratorów metod zastosowano prostszą formę funkcyjną (`requires_config`).

3. **Serializowalność funkcji w `multiprocessing`.** Lambdy i funkcje zagnieżdżone nie mogą być przekazane do `ProcessPoolExecutor` (wymóg `pickle`). Rozwiązanie: `_hash_file_for_process` jest funkcją zdefiniowaną na poziomie modułu, przyjmującą krotkę argumentów.
