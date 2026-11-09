# Leaflet 1.9.4

Cópia sem alterações de `dist/leaflet.js` e `dist/leaflet.css` do
[Leaflet](https://leafletjs.com) 1.9.4 (licença BSD de 2 cláusulas, em
`LICENSE`), baixada de `https://unpkg.com/leaflet@1.9.4/dist/`. Fica no
projeto para a interface não depender de CDN; só as imagens das ruas
(OpenStreetMap) vêm da internet.

Integridade (os mesmos hashes publicados em leafletjs.com/download.html):

    leaflet.js   sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=
    leaflet.css  sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=

Conferir: `openssl dgst -sha256 -binary leaflet.js | base64`
