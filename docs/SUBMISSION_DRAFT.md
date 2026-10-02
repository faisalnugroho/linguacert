# SUBMISSION DRAFT — LinguaCert (final, verified against live chain)

## Kategori
Builder → Intelligent Contracts

## Judul
LinguaCert — Trustless Translation Certification

## One-liner
Kontrak pintar GenLayer yang mensertifikasi terjemahan lewat konsensus:
forensik teks deterministik (preservasi angka/URL/placeholder) + LLM
menilai fidelity per-kriteria dengan sitasi verbatim yang diverifikasi
on-chain; verdict selalu diturunkan kontrak, never the model.

## Deskripsi (target ≤1000 char — hitung ulang sebelum submit)
Klien mengunci source text + kandidat terjemahan (hash-pinned di GitHub,
immutable commit URL) + kriteria penerimaan natural-language. Resolusi
menggabungkan dua lapisan: (1) forensik deterministik oleh kontrak —
setiap angka, URL, dan placeholder di source harus dipertahankan
(separator-insensitive 1,000 == 1.000; enumerator markdown dikecualikan),
pelanggaran memaksa REJECTED apa pun kata model; (2) penilaian LLM
per-kriteria PASS/FAIL/UNCERTAIN di mana setiap PASS wajib berdiri di
kutipan verbatim TERJEMAHAN itu sendiri dan setiap kutipan direvalidasi
on-chain terhadap byte yang di-fetch. Semua mode kegagalan LLM (exception,
non-JSON, bukti mati/tampered/oversized/thin) fail-safe ke INCONCLUSIVE.
Challenge period + dispute window (clock node), budget fetch adil,
registry digest tersertifikasi tunggal. Bukti live (Studionet): 3 job
good berdigest beda semua APPROVED, 1 negative REJECTED, guard
single-certification live; riwayat INCONCLUSIVE tetap on-chain sebagai
bukti fail-safe.

## Mengapa butuh GenLayer
Keputusan kualitas terjemahan menentukan apakah kerja diterima — klien
dan penerjemah adalah pihak yang berlawanan, jadi satu panggilan LLM API
dari salah satu sisi tidak membuktikan apa pun. Validator GenLayer
mengeksekusi ulang evaluasi yang sama dan hanya konvergen pada substansi
stabil yang didukung bukti publik re-fetchable.

## Repo
https://github.com/faisalnugroho/linguacert (bukti + kode diverifikasi
pada commit 52a1e4cdd5eef907c943a24ca0dcf569cab2d2f9; edits setelahnya
docs-only)

## Kontrak live (Studionet)
- Address: 0x47a503A6aFe396525dd02C61c44A25fa72BcbB6c
- Explorer: https://explorer-studio.genlayer.com/contracts/0x47a503A6aFe396525dd02C61c44A25fa72BcbB6c
- Deploy tx: 0xab9f341503b7fc72a9fc13f37d5a22ab68f0d6db4a2a44e030aeaff5152d4491
- Deployed code == repo (sha256 proof): 6b71c663364365b0b4e034c7c38e9690aa484f5547eecc8b8f452583ebad7a37
  = sha256(contracts/linguacert.py) di commit 52a1e4c — byte-identical,
  dibuktikan dari data.contract_code di deploy tx; tidak ada commit yang
  menyentuh contracts/ setelah deploy (git log 93e24b0..HEAD -- contracts/ kosong)

## Bukti transaksi (semua tx diverifikasi via explorer API + decode calldata)
| Skenario | Job | Open tx | Resolve tx | Hasil |
|---|---|---|---|---|
| Determinism 1 | smoke-good-1 | 0x3474681bc479f3222b8781c5509f975c29bee47256068d44038f4087a7c3a3e3 | 0xd09e1a883e0ee77581a93de4140d51edea6f774efcf38f8107525cda2357e686 | APPROVED |
| Determinism 2 | smoke-good-2f | 0xffb4d58e0132e3bbbf275b972eae1b24d6dbb46e4252a2f8f674c6e6930043f0 | 0xc876ce49020a734e1370b73b64fd92e954adc5dcaa3301e3038f1fa2c4282ad6 | APPROVED (PASS x3, 1 round) |
| Determinism 3 | smoke-good-3h | 0x0f19f68e5e667858a44ebd028a203f3a8727f9ad4f10d355c391663445beb3e4 | 0x1d7b6299ad357e1eac1c20cd2506e157670112692e1b61e87d387ed4e331747a | APPROVED (PASS x3, 1 round) |
| Negative (nilai di-drop) | smoke-bad-1 | 0x859e30bf914bcc0811c5be03cda8a1e00474bcb40f11903cf10b80d3e426d7b8 | 0x92f607e56caad6785b317e68a4ead0409d4262f52cbacd0588419d6dafc6b756 | REJECTED |
| Guard single-certification | resolve(smoke-good-2) | — | 0xebd550caefbae778a76b816608b9bf43aeb0dc03ec8b9d451e469b1833efe99a | MAJORITY_AGREE + exec ERROR, reason `already_certified` |

## Riwayat INCONCLUSIVE (kejujuran — terminal, tetap on-chain)
smoke-good-2b/3c/2d/3e: terjemahan melepas struktur kalimat sumber sehingga
tak ada satu kutipan yang membawa SEMUA angka → model konservatif menandai
criterion 0 UNCERTAIN (fail-safe by design). smoke-good-3g: mirror-style
namun model salah atribusi indeks kriteria pada kutipan (criterion 1
alih-alih 0) → INCONCLUSIVE. Analisis akar masalah + konvensi sitasi ada
di `criteria_note` docs/deployment_log.json. INCONCLUSIVE adalah hasil
kelas-satu yang dirancang: yang tak terbukti tidak pernah tersertifikasi.

## Test & lint (dijalankan ulang fresh saat audit submit)
- 73/73 direct-mode tests (real GenVM, web/LLM mocked): `pytest tests/direct/ -q`
- genvm-lint: 3/3 checks passed + validasi SDK, kontrak valid (9 metode)

## Scope notes (kejujuran)
- Sertifikasi = opini kualitas konsensus validator, BUKAN pengganti
  terjemahan tersumpah/manusiawi.
- Kriteria ditulis klien; kontrak tidak menilai k fairness kriteria.
- Forensik mencakup angka/URL/placeholder + metadata panjang — bukan
  fidelity semantik penuh (itu tugas lapisan LLM).
