# 005 — XMP `darktable:params` encoding (verified)

Worker: W4 (`feat/xmp-codecs`). Confirms plan §7.1's description against
darktable's actual source and documents the exact algorithm implemented in
`helper/dt_ai_helper/xmp.py::decode_params_blob`.

## Where verified

`src/common/exif.cc` at tag `release-4.6.0`
(https://raw.githubusercontent.com/darktable-org/darktable/release-4.6.0/src/common/exif.cc),
functions `dt_exif_xmp_encode` / `dt_exif_xmp_encode_internal` (~line 2599)
and `dt_exif_xmp_decode` (~line 2699).

## The algorithm

`darktable:params` and `darktable:blendop_params` text values are one of:

1. **Plain hex** — lowercase hex of the raw struct bytes, no prefix. This
   is what darktable writes when the `compress_xmp_tags` preference is
   `"no"`, or `"only large entries"` and the blob is `<= 100` bytes.

2. **`gz`-prefixed** — `"gz"` + a **2-digit decimal expansion factor** +
   **base64 of the zlib-compressed bytes**. Written when
   `compress_xmp_tags` is `"always"`, or `"only large entries"` (the
   default) and the raw blob is `> 100` bytes (`#define
   COMPRESS_THRESHOLD 100` in exif.cc, compared against the *uncompressed*
   length).

   Encode (`dt_exif_xmp_encode_internal`, `do_compress == TRUE`):
   ```c
   uLongf destLen = compressBound(len);
   compress(buffer1, &destLen, input, len);       // zlib deflate, WITH zlib header
   const int factor = MIN(len / destLen + 1, 99);  // expansion factor, clamped to 99
   char *b64 = g_base64_encode(buffer1, destLen);
   output = "gz" + two-digit-zero-padded(factor) + b64;
   ```

   Decode (`dt_exif_xmp_decode`):
   ```c
   if (!strncmp(input, "gz", 2)) {
     factor = 10*(input[2]-'0') + (input[3]-'0');   // the 2 digits right after "gz"
     base64_decode(input + 4);                       // everything after "gz" + 2 digits
     uncompress(...);                                 // zlib inflate, WITH zlib header
   }
   ```

   **Critical detail**: `compress()`/`uncompress()` are zlib's own wrapper
   functions, which produce/expect the *zlib* format (2-byte header +
   deflate stream + Adler-32 trailer) — **not** raw deflate and **not**
   gzip. In Python this is exactly `zlib.compress()` / `zlib.decompress()`
   with default arguments (no negative `wbits`, no `gzip` module). Do not
   use `zlib.decompressobj(wbits=-15)` (raw deflate) or the `gzip` module
   here — both would fail or silently produce garbage.

   The "factor" byte pair is purely an allocation hint for the C decoder
   (so it can size its `malloc` before calling `uncompress`); Python's
   `zlib.decompress` doesn't need a size hint, so on decode we simply
   ignore those two digits and pass everything after them to
   `base64.b64decode` then `zlib.decompress`. On encode we still write a
   correct factor for interop/round-trip fidelity with real darktable,
   computed the same way: `min(len(raw) // max(len(compressed), 1) + 1,
   99)`.

## Implementation

- `helper/dt_ai_helper/xmp.py::decode_params_blob(text)` — the decode
  half; returns `None` (never raises) on empty/malformed input.
- `tests/fixtures/make_fixtures.py::encode_field` — the encode half, used
  to build the `generated_tier1.xmp` fixture. Mirrors darktable's actual
  compress-vs-plain-hex decision (`> 100` raw bytes → gz) so the fixture
  exercises both code paths realistically: `exposure`/`temperature`/
  `sharpen`/`highlights`/`sigmoid`/`toneequal`/`crop` (all ≤ 100 bytes)
  come out as plain hex, `filmicrgb`/`colorbalancergb`/`denoiseprofile`
  (all > 100 bytes) come out as `gz`.

## Outstanding: no real darktable XMP validated yet

This environment has no darktable install, so everything above is
verified **against darktable's own encoder/decoder source**, and the test
fixtures are self-consistent (our encoder → our decoder), but **no actual
darktable-produced sidecar has been run through this parser**. Two things
in particular still need real-file validation:

1. **XML shape of `<rdf:li>` entries.** `xmp.py` assumes (based on general
   knowledge of darktable sidecars, not a captured sample) that each
   history entry's fields are XML *attributes* directly on `<rdf:li
   darktable:operation="..." .../>`. It defensively also accepts the
   equivalent child-element form (`<rdf:li><darktable:operation>...`) in
   case a different Exiv2/serializer version emits that instead — but this
   has not been checked against a byte-for-byte real file.
2. **The gz encoding path itself** on a real darktable install, to confirm
   no dt-version-specific wrinkle exists (e.g. some 5.x change to
   `compress_xmp_tags` defaults or the threshold constant).

**Manual task for a future worker/human**: open darktable 4.6+ and 5.x,
apply a few Tier-1 module edits with known slider values, let it write the
`.xmp` sidecar (or trigger "write sidecar files"), and drop the file next
to a YAML of the values set in the GUI into `tests/fixtures/`. Compare
against this doc's algorithm and fix any discrepancy found.
