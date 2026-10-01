# SUBMISSION DRAFT — LinguaCert (isi tx hashes setelah smoke)

## Kategori
Builder → Intelligent Contracts

## Judul
LinguaCert — Trustless Translation Certification

## One-liner
Kontrak pintar GenLayer yang mensertifikasi terjemahan lewat konsensus:
forensik teks deterministik (preservasi angka/URL/placeholder) + LLM
menilai fidelity per-kriteria dengan sitasi verbatim yang diverifikasi
on-chain; verdict selalu diturunkan kontrak, never the model.

## Deskripsi (≤1000 char — hitung ulang sebelum submit)
Klien mengunci source text + kandidat terjemahan (hash-pinned di GitHub,
immutcommit URL) + kriteria penerimaan natural-language. Resolusi
menggabungkan dua lapisan: (1) forensik deterministik oleh kontrak —
setiap angka, URL, dan placeholder di source harus dipertahankan
(separator-insensitive 1,000 == 1.000; enumerator markdown dikecualikan),
pelanggaran memaksa REJECTED apa pun kata model; (2) penilaian LLM
per-kriteria PASS/FAIL/UNCERTAIN di mana setiap PASS wajib berdiri di
kutipan verbatim TERJEMAHAN itu sendiri dan setiap kutipan direvalidasi
on-chain terhadap byte yang di-fetch. Semua mode kegagalan LLM (exception,
non-JSON, bukti mati/tampered/oversized/thin) fail-safe ke INCONCLUSIVE.
Challenge period + dispute window dengan clock node, budget fetch adil,
registry digest tersertifikasi tunggal. Bukti live: kontrak di
Studionet, 3x determinism run APPROVED + 1 negative REJECTED, semua tx
hash tercantum di bawah.

## Mengapa butuh GenLayer
Keputusan kualitas terjemahan menentukan apakah kerja diterima — klien
dan penerjemah adalah pihak yang berlawanan, jadi satu panggilan LLM API
dari salah satu sisi tidak membuktikan apa pun. Validator GenLayer
mengeksekusi ulang evaluasi yang sama dan hanya konvergen pada substansi
stabil yang didukung bukti publik re-fetchable.

## Repo
https://github.com/faisalnugroho/linguacert

## Kontrak live (Studionet)
- Address: TO_BE_FILLED
- Explorer: https://explorer-studio.genlayer.com/contracts/TO_BE_FILLED
- Deploy tx: TO_BE_FILLED
- Deployed code == repo (sha256 proof): TO_BE_FILLED

## Bukti transaksi (tx hashes)
| Skenario | Job | Tx | Hasil |
|---|---|---|---|
| Determinism 1 | smoke-good-1 | TO_BE_FILLED | APPROVED |
| Determinism 2 | smoke-good-2 | TO_BE_FILLED | APPROVED |
| Determinism 3 | smoke-good-3 | TO_BE_FILLED | APPROVED |
| Negative (nilai di-drop) | smoke-bad-1 | TO_BE_FILLED | REJECTED |

## Test & lint
- 73/73 direct-mode tests (real GenVM, web/LLM mocked): jalankan
  `pytest tests/direct/ -q`
- genvm-lint: 3/3 checks passed, kontrak valid (9 metode)

## Scope notes (kejujuran)
- Sertifikasi = opini kualitas konsensus validator, BUKAN pengganti
  terjemahan tersumpah/manusiawi.
- Kriteria ditulis klien; kontrak tidak menilai k fairness kriteria.
- Forensik mencakup angka/URL/placeholder + metadata panjang — bukan
  fidelity semantik penuh (itu tugas lapisan LLM).
