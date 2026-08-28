(function () {
    function formatLatLng(latlng) {
        if (!latlng || !isFinite(latlng.lat) || !isFinite(latlng.lng)) {
            return '';
        }
        return Number(latlng.lat).toFixed(6) + ',' + Number(latlng.lng).toFixed(6);
    }

    function applyClickPositioning(mapId) {
        const valueInput = document.getElementById(mapId + '_value');
        const mapContainer = document.getElementById(mapId + '_map');
        if (!valueInput || !mapContainer || !mapContainer._leaflet_map) {
            return;
        }

        const map = mapContainer._leaflet_map;
        if (map._loebClickPositioningEnabled) {
            return;
        }
        map._loebClickPositioningEnabled = true;

        const updateValue = function (latlng) {
            const value = formatLatLng(latlng);
            if (!value) {
                return;
            }
            valueInput.value = value;
            valueInput.dispatchEvent(new Event('change', { bubbles: true }));
        };

        const ensureMarker = function () {
            if (map._loebClickMarker) {
                return map._loebClickMarker;
            }
            const marker = L.marker(map.getCenter(), { draggable: true });
            marker.on('move', function (event) {
                updateValue(event.latlng);
            });
            map.addLayer(marker);
            map._loebClickMarker = marker;
            return marker;
        };

        map.on('click', function (event) {
            const marker = ensureMarker();
            marker.setLatLng(event.latlng);
            updateValue(event.latlng);
        });
    }

    function hookMapLocationInit() {
        const original = window.MapLocationInit;
        if (original) {
            window.MapLocationInit = function (mapId, options) {
                original(mapId, options);
                setTimeout(function () {
                    applyClickPositioning(mapId);
                }, 300);
            };
        }
    }

    function initAllMapLocationWidgets() {
        document.querySelectorAll('[id$="_map"]').forEach(function (mapElement) {
            const mapId = mapElement.id.replace(/_map$/, '');
            applyClickPositioning(mapId);
        });
    }

    hookMapLocationInit();
    document.addEventListener('DOMContentLoaded', initAllMapLocationWidgets);
    window.addEventListener('load', initAllMapLocationWidgets);
})();
