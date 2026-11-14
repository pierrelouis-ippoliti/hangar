# PDF fixture

`faa-h-8083-30b-p34-36.pdf` holds pages 34 to 36 of the FAA Aviation Maintenance Technician Handbook – General (FAA-H-8083-30B), printed as pages 1-13 to 1-15. It is a work of the United States Government, with no copyright. The pages hold text only, with no figures credited to outside contributors.

It was cut from the C1 file with:

```sh
qpdf --empty --pages data/raw/faa-h-8083-30b.pdf 34-36 -- tests/fixtures/pdf/faa-h-8083-30b-p34-36.pdf
```

qpdf keeps the page labels. Page 35 has one hyphen that PDFium reports as `U+FFFE`, in "self-sustaining".
