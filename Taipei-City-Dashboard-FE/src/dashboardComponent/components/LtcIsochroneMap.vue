<!-- Developed by codefest2026-wage-slave 2026 -->
<!-- LtcIsochroneMap: 長照可及性等時圈互動組件 -->
<!-- 使用 Mapbox Isochrone API 計算步行可達範圍，疊加長照機構點位 -->

<script setup>
import { ref, onMounted, onUnmounted, inject } from "vue";
import mapboxGl from "mapbox-gl";

const props = defineProps(["chart_config", "series"]);

// ── State ──────────────────────────────────────────────────
const address = ref("");
const isLoading = ref(false);
const errorMsg = ref("");
const result = ref(null);
const mapContainer = ref(null);

let map = null;
let geocoderResult = null;

// ── Mapbox token ───────────────────────────────────────────
const MAPBOXTOKEN = import.meta.env.VITE_MAPBOXTOKEN;

// Isochrone contour colours for 5 / 10 / 15 min
const ISOCHRONE_COLORS = {
	5: "#2EC4B6",
	10: "#F77F00",
	15: "#D62828",
};

// ── Lifecycle ──────────────────────────────────────────────
onMounted(() => {
	if (!MAPBOXTOKEN) return;
	mapboxGl.accessToken = MAPBOXTOKEN;
	map = new mapboxGl.Map({
		container: mapContainer.value,
		style: `${import.meta.env.VITE_MAPBOXTILE}`,
		center: [121.517, 25.047],
		zoom: 11,
	});
	map.addControl(new mapboxGl.NavigationControl(), "top-right");
});

onUnmounted(() => {
	if (map) {
		map.remove();
		map = null;
	}
});

// ── Geocode address via Mapbox Geocoding API ───────────────
async function geocodeAddress(addr) {
	const url = `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(
		addr
	)}.json?country=TW&language=zh&access_token=${MAPBOXTOKEN}&limit=1`;
	const res = await fetch(url);
	const data = await res.json();
	if (!data.features || data.features.length === 0) {
		throw new Error(`找不到地址：${addr}`);
	}
	return data.features[0].center; // [lng, lat]
}

// ── Fetch Isochrone polygons ────────────────────────────────
async function fetchIsochrone(lng, lat) {
	const minutes = "5,10,15";
	const url =
		`https://api.mapbox.com/isochrone/v1/mapbox/walking/${lng},${lat}` +
		`?contours_minutes=${minutes}&polygons=true&access_token=${MAPBOXTOKEN}`;
	const res = await fetch(url);
	if (!res.ok) throw new Error("Isochrone API 失敗，請稍後再試。");
	return res.json();
}

// ── Fetch LTC facility points from backend ─────────────────
async function fetchLtcPoints() {
	try {
		const res = await fetch("/api/v1/map/ltc_care_newtpe");
		if (!res.ok) return null;
		return res.json();
	} catch {
		return null;
	}
}

// ── Count facilities inside each isochrone polygon ─────────
function countInPolygon(geoJson, points) {
	if (!geoJson || !points) return {};
	const turf = window.turf;
	if (!turf) return {};
	const counts = {};
	for (const feat of geoJson.features) {
		const mins = feat.properties.contour;
		let c = 0;
		for (const pt of (points.features || [])) {
			try {
				if (turf.booleanPointInPolygon(pt, feat)) c++;
			} catch {
				// skip invalid geometry
			}
		}
		counts[mins] = c;
	}
	return counts;
}

// ── Draw layers on map ─────────────────────────────────────
function drawLayers(isoGeoJson, ltcGeoJson, center) {
	if (!map) return;

	// Remove old layers / sources
	["iso-fill-15", "iso-fill-10", "iso-fill-5", "iso-outline"].forEach((id) => {
		if (map.getLayer(id)) map.removeLayer(id);
	});
	["isochrone", "ltc-points", "origin"].forEach((id) => {
		if (map.getSource(id)) map.removeSource(id);
	});

	// Isochrone fill layers (draw largest first)
	map.addSource("isochrone", { type: "geojson", data: isoGeoJson });
	for (const mins of [15, 10, 5]) {
		map.addLayer({
			id: `iso-fill-${mins}`,
			type: "fill",
			source: "isochrone",
			filter: ["==", ["get", "contour"], mins],
			paint: {
				"fill-color": ISOCHRONE_COLORS[mins],
				"fill-opacity": 0.25,
			},
		});
	}
	map.addLayer({
		id: "iso-outline",
		type: "line",
		source: "isochrone",
		paint: { "line-color": "#ffffff", "line-width": 1.5, "line-opacity": 0.6 },
	});

	// LTC facility points
	if (ltcGeoJson) {
		map.addSource("ltc-points", { type: "geojson", data: ltcGeoJson });
		map.addLayer({
			id: "ltc-layer",
			type: "circle",
			source: "ltc-points",
			paint: {
				"circle-radius": 6,
				"circle-color": "#2E86AB",
				"circle-stroke-width": 1.5,
				"circle-stroke-color": "#ffffff",
			},
		});
	}

	// Origin marker
	map.addSource("origin", {
		type: "geojson",
		data: { type: "Feature", geometry: { type: "Point", coordinates: center } },
	});
	map.addLayer({
		id: "origin-layer",
		type: "circle",
		source: "origin",
		paint: {
			"circle-radius": 8,
			"circle-color": "#D62828",
			"circle-stroke-width": 2,
			"circle-stroke-color": "#ffffff",
		},
	});

	map.flyTo({ center, zoom: 14 });
}

// ── Main search handler ────────────────────────────────────
async function search() {
	if (!address.value.trim()) return;
	isLoading.value = true;
	errorMsg.value = "";
	result.value = null;

	try {
		const [lng, lat] = await geocodeAddress(address.value);
		const [isoGeoJson, ltcGeoJson] = await Promise.all([
			fetchIsochrone(lng, lat),
			fetchLtcPoints(),
		]);

		const counts = countInPolygon(isoGeoJson, ltcGeoJson);
		result.value = {
			count5min: counts[5] ?? "–",
			count10min: counts[10] ?? "–",
			count15min: counts[15] ?? "–",
		};

		drawLayers(isoGeoJson, ltcGeoJson, [lng, lat]);
	} catch (err) {
		errorMsg.value = err.message || "查詢失敗，請稍後再試。";
	} finally {
		isLoading.value = false;
	}
}
</script>

<template>
	<div class="ltc-isochrone">
		<!-- Search Bar -->
		<div class="search-bar">
			<input
				v-model="address"
				class="address-input"
				placeholder="輸入地址查詢長照可及性（例：新北市板橋區文化路一段100號）"
				:disabled="isLoading"
				@keyup.enter="search"
			/>
			<button class="search-btn" :disabled="isLoading" @click="search">
				<span v-if="isLoading">查詢中…</span>
				<span v-else>查詢</span>
			</button>
		</div>

		<!-- Error Message -->
		<p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>

		<!-- Map Container -->
		<div ref="mapContainer" class="map-container" />

		<!-- Result Card -->
		<div v-if="result" class="result-card">
			<h3>步行可達長照機構數</h3>
			<div class="result-rows">
				<div class="result-row">
					<span class="dot" style="background:#2EC4B6" />
					<span>5 分鐘步行範圍內：<strong>{{ result.count5min }}</strong> 間</span>
				</div>
				<div class="result-row">
					<span class="dot" style="background:#F77F00" />
					<span>10 分鐘步行範圍內：<strong>{{ result.count10min }}</strong> 間</span>
				</div>
				<div class="result-row">
					<span class="dot" style="background:#D62828" />
					<span>15 分鐘步行範圍內：<strong>{{ result.count15min }}</strong> 間</span>
				</div>
			</div>
			<p class="hotline-hint">
				如需更多長照資源協助，請撥打
				<a href="tel:1966" class="hotline">☎ 1966</a> 長照專線
			</p>
		</div>

		<!-- Placeholder when no result -->
		<div v-else-if="!isLoading" class="placeholder">
			<p>輸入地址後按「查詢」，即可看到步行 5 / 10 / 15 分鐘可達的長照機構分布。</p>
		</div>
	</div>
</template>

<style scoped>
.ltc-isochrone {
	display: flex;
	flex-direction: column;
	gap: 0.75rem;
	height: 100%;
	padding: 0.5rem;
}

.search-bar {
	display: flex;
	gap: 0.5rem;
}

.address-input {
	flex: 1;
	padding: 0.4rem 0.6rem;
	border: 1px solid var(--color-border, #ccc);
	border-radius: 4px;
	font-size: 0.85rem;
	background: var(--color-surface, #1e1e1e);
	color: var(--color-text, #fff);
}

.search-btn {
	padding: 0.4rem 0.9rem;
	border: none;
	border-radius: 4px;
	background: #2e86ab;
	color: #fff;
	cursor: pointer;
	font-size: 0.85rem;
	white-space: nowrap;
}

.search-btn:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}

.map-container {
	flex: 1;
	min-height: 260px;
	border-radius: 6px;
	overflow: hidden;
}

.result-card {
	background: var(--color-surface, #1e1e1e);
	border: 1px solid var(--color-border, #333);
	border-radius: 6px;
	padding: 0.75rem;
}

.result-card h3 {
	margin: 0 0 0.5rem;
	font-size: 0.9rem;
	color: var(--color-text, #fff);
}

.result-rows {
	display: flex;
	flex-direction: column;
	gap: 0.3rem;
}

.result-row {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	font-size: 0.85rem;
	color: var(--color-text-secondary, #ccc);
}

.dot {
	width: 10px;
	height: 10px;
	border-radius: 50%;
	flex-shrink: 0;
}

.hotline-hint {
	margin: 0.5rem 0 0;
	font-size: 0.78rem;
	color: var(--color-text-secondary, #aaa);
}

.hotline {
	color: #2ec4b6;
	text-decoration: none;
}

.error-msg {
	color: #d62828;
	font-size: 0.82rem;
	margin: 0;
}

.placeholder {
	padding: 0.5rem;
	font-size: 0.82rem;
	color: var(--color-text-secondary, #aaa);
}
</style>
