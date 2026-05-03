// Taipei-City-Dashboard-FE/src/store/foodSafetyStore.js
// Pinia store for dashboard 504 (食安監控系統).
// Manages: active layer (school|restaurant), selection focus, mock data cache,
// search/filter state, and orchestrates mapStore add/remove/redraw operations.

import { defineStore } from "pinia";
import axios from "axios";
import { useMapStore } from "./mapStore";

const MOCK_BASE = "/mockData/food_safety_monitor";

export const useFoodSafetyStore = defineStore("foodSafety", {
	state: () => ({
		// Mode (mutex toggle result; null = neither layer active)
		activeLayer: null,            // 'school' | 'restaurant' | null

		// Single covering analysis focus (covers school | supplier | incident)
		analysisFocus: null,          // { type, payload } | null

		// Restaurant selection (independent panel)
		selectedRestaurant: null,

		// School map UX
		schoolSearchQuery: "",

		// Restaurant map UX
		restaurantSearchQuery: "",
		restaurantFilters: {
			district: "all",
			severity: "all",
			timeRange: "1y",
		},

		// Mock data cache (lazy-populated by loadAllMockData())
		schools: [],
		suppliers: [],
		supplyChain: [],
		incidents: [],
		districtHeatmap: null,
		restaurants: [],
		restaurantInspections: {},
		supplierAudits: {},
		schoolNutrition: {},

		// Loading flags
		loading: {
			schools: false, suppliers: false, supplyChain: false,
			incidents: false, districtHeatmap: false,
			restaurants: false, restaurantInspections: false,
			supplierAudits: false, schoolNutrition: false,
		},
		loadedAt: null,
	}),

	getters: {
		// Filtered schools matching current search query (for SchoolSearchBar dropdown)
		schoolSearchResults(state) {
			const q = state.schoolSearchQuery.trim();
			if (!q) return [];
			return state.schools.filter(
				(f) => f.properties.name.includes(q),
			).slice(0, 8);
		},
		// Filtered restaurants matching current search query
		restaurantSearchResults(state) {
			const q = state.restaurantSearchQuery.trim();
			if (!q) return [];
			return state.restaurants.filter(
				(f) => (f.properties.name || "").includes(q)
					|| (f.properties.address || "").includes(q),
			).slice(0, 8);
		},
		// Recent N incidents sorted by date desc (RecentIncidentsStrip)
		recentIncidents(state) {
			return [...state.incidents].sort(
				(a, b) => b.occurred_at.localeCompare(a.occurred_at),
			);
		},
		// Stats for ExternalStatsStrip (校外底部 4 張卡).
		// Real-data shape: every business in restaurants.geojson already has
		// at least one FAIL inspection; hazard_level = max severity recorded.
		externalStats(state) {
			const total = state.restaurants.length;
			const totalFails = state.restaurants.reduce(
				(s, f) => s + (f.properties.fail_count || 0), 0,
			);
			const critical = state.restaurants.filter(
				(f) => f.properties.hazard_level === "critical",
			).length;
			const highRiskDistricts = new Set(
				state.restaurants
					.filter((f) => f.properties.hazard_level === "critical"
						|| f.properties.hazard_level === "high")
					.map((f) => f.properties.district),
			).size;
			return { total, fail: totalFails, critical, highRiskDistricts };
		},
	},

	actions: {
		// Register a programmatically-drawn truck silhouette as a Mapbox SDF
		// image. Idempotent — safe to call multiple times. The SDF mode lets us
		// tint the icon per-feature via paint icon-color.
		_ensureTruckImage() {
			const mapStore = useMapStore();
			const m = mapStore.map;
			if (!m || m.hasImage("fsm-truck")) return;
			const size = 32;
			const canvas = document.createElement("canvas");
			canvas.width = size;
			canvas.height = size;
			const ctx = canvas.getContext("2d");
			ctx.fillStyle = "#000";
			// Cab
			ctx.fillRect(2, 12, 8, 10);
			// Cargo box
			ctx.fillRect(11, 8, 17, 14);
			// Wheels (filled circles)
			ctx.beginPath();
			ctx.arc(7, 25, 2.5, 0, Math.PI * 2);
			ctx.arc(22, 25, 2.5, 0, Math.PI * 2);
			ctx.fill();
			const imageData = ctx.getImageData(0, 0, size, size);
			m.addImage("fsm-truck", imageData, { sdf: true });
		},

		// ── Loading ─────────────────────────────────────────────
		async loadAllMockData() {
			if (this.loadedAt) return;
			const fetchJson = async (file, key) => {
				this.loading[key] = true;
				try {
					const r = await axios.get(`${MOCK_BASE}/${file}`);
					return r.data;
				} finally {
					this.loading[key] = false;
				}
			};
			const [schools, suppliers, chain, incidents, heat, rest, insp] =
				await Promise.all([
					fetchJson("schools.geojson", "schools"),
					fetchJson("suppliers.geojson", "suppliers"),
					fetchJson("supply_chain.geojson", "supplyChain"),
					fetchJson("incidents.json", "incidents"),
					fetchJson("district_heatmap.geojson", "districtHeatmap"),
					fetchJson("restaurants.geojson", "restaurants"),
					fetchJson("restaurant_inspections.json", "restaurantInspections"),
				]);
			const [audits, nutrition] = await Promise.all([
				fetchJson("supplier_audits.json", "supplierAudits"),
				fetchJson("school_nutrition.json", "schoolNutrition"),
			]);
			this.schools = schools.features;
			this.suppliers = suppliers.features;
			this.supplyChain = chain.features;
			this.incidents = incidents;
			this.districtHeatmap = heat;
			this.restaurants = rest.features;
			this.restaurantInspections = insp;
			this.supplierAudits = audits;
			this.schoolNutrition = nutrition;
			this.loadedAt = Date.now();
		},

		// ── Mutex layer toggle ──────────────────────────────────
		setActiveLayer(layer) {
			const mapStore = useMapStore();
			if (this.activeLayer === layer) {
				// toggle off
				this._removeLayerGroup(this.activeLayer, mapStore);
				this.activeLayer = null;
				this.analysisFocus = null;
				this.selectedRestaurant = null;
				return;
			}
			// switching: remove previous group, then add new
			if (this.activeLayer) {
				this._removeLayerGroup(this.activeLayer, mapStore);
			}
			this.activeLayer = layer;
			// New layer added by Mapbox via dashboard's normal toggle pipeline;
			// nothing extra here. Panels reactively render via watch on activeLayer.
			if (layer === "restaurant") {
				// After Mapbox/dashboard adds the district fill layer, raise the
				// town label so labels stay visible on top of choropleth (R4).
				setTimeout(() => this._raiseTownLabel(mapStore), 600);
			}
		},

		_raiseTownLabel(mapStore) {
			const m = mapStore.map;
			if (!m) return;
			try {
				if (m.getLayer("metrotaipei_town_label-symbol")) {
					m.moveLayer("metrotaipei_town_label-symbol");
				}
			} catch { /* layer not present yet — no-op */ }
		},

		// Per-layer city filter: derive the layer's city from its own layerId
		// (`${index}-${type}-${city}` per mapStore convention) and apply the
		// matching Mapbox setFilter. Self-contained — no external "current
		// city" state needed. Run this whenever currentLayers changes; it's
		// safe to call multiple times.
		applyCityFilter() {
			const mapStore = useMapStore();
			if (!mapStore.map) return;
			const cityToName = (c) =>
				c === "taipei" ? "臺北市" :
					c === "ntpc" ? "新北市" : null;
			const cityFromLayerId = (l) => {
				const parts = l.split("-");
				return parts[parts.length - 1];
			};
			const FSM_FIELDS = {
				fsm_schools: "city",
				fsm_restaurants: "city",
				fsm_suppliers: "city",
				fsm_supplier_dots: "city",
				fsm_district_heat: "PNAME",
			};
			Object.entries(FSM_FIELDS).forEach(([idx, field]) => {
				mapStore.currentLayers
					.filter((l) => l.startsWith(`${idx}-`))
					.forEach((l) => {
						if (!mapStore.map.getLayer(l)) return;
						const cityName = cityToName(cityFromLayerId(l));
						mapStore.map.setFilter(
							l,
							cityName ? ["==", ["get", field], cityName] : null,
						);
					});
			});
		},

		applyRestaurantFilters() {
			const mapStore = useMapStore();
			const layer = mapStore.currentLayers.find((l) => l.startsWith("fsm_restaurants-"));
			if (!layer || !mapStore.map?.getLayer(layer)) return;
			const f = this.restaurantFilters;
			const conditions = [];
			// District: 'all' | '臺北市' | '新北市' | <district name>
			if (f.district === "臺北市" || f.district === "新北市") {
				conditions.push(["==", ["get", "city"], f.district]);
			} else if (f.district !== "all") {
				conditions.push(["==", ["get", "district"], f.district]);
			}
			// Severity: 'all' | 'high' (critical+high) | 'medium' | 'low' (low+info)
			if (f.severity === "high") {
				conditions.push(["match", ["get", "hazard_level"], ["critical", "high"], true, false]);
			} else if (f.severity === "medium") {
				conditions.push(["==", ["get", "hazard_level"], "medium"]);
			} else if (f.severity === "low") {
				conditions.push(["match", ["get", "hazard_level"], ["low", "info"], true, false]);
			}
			// timeRange currently has no per-feature aggregate (we'd have to join
			// to inspection history), so the filter is captured in state but does
			// not constrain the Mapbox layer.
			const expr =
				conditions.length === 0 ? null :
					conditions.length === 1 ? conditions[0] :
						["all", ...conditions];
			mapStore.map.setFilter(layer, expr);
		},

		_removeLayerGroup(layer, mapStore) {
			// Remove selection labels (created by _drawSelectionLabels)
			if (mapStore.map) {
				if (mapStore.map.getLayer("fsm_selection_labels-layer")) {
					mapStore.map.removeLayer("fsm_selection_labels-layer");
				}
				if (mapStore.map.getSource("fsm_selection_labels-source")) {
					mapStore.map.removeSource("fsm_selection_labels-source");
				}
				if (mapStore.map.getLayer("fsm_selected-layer")) {
					mapStore.map.removeLayer("fsm_selected-layer");
				}
				if (mapStore.map.getSource("fsm_selected-source")) {
					mapStore.map.removeSource("fsm_selected-source");
				}
				["fsm_connected_suppliers-truck", "fsm_connected_suppliers-halo"].forEach((id) => {
					if (mapStore.map.getLayer(id)) mapStore.map.removeLayer(id);
				});
				if (mapStore.map.getSource("fsm_connected_suppliers-source")) {
					mapStore.map.removeSource("fsm_connected_suppliers-source");
				}
			}
			const ids =
				layer === "school"
					? ["fsm_schools", "fsm_supply_chain", "fsm_suppliers", "fsm_supplier_dots"]
					: ["fsm_restaurants", "fsm_district_heat"];
			ids.forEach((idx) => {
				// mapStore.currentLayers entries are `${index}-${type}-${city}`,
				// match by prefix.
				const matching = mapStore.currentLayers.filter(
					(l) => l.startsWith(`${idx}-`),
				);
				matching.forEach((l) => {
					const cfg = mapStore.mapConfigs[l];
					if (cfg) mapStore.removeMapLayer(cfg);
				});
			});
		},

		// ── Selection ───────────────────────────────────────────
		setAnalysisFocus(type, payload) {
			this.analysisFocus = { type, payload };
		},

		selectSchool(school) {
			this.setAnalysisFocus("school", school);
			const arcs = this.supplyChain.filter(
				(f) => f.properties.school_id === school.properties.id,
			);
			this.redrawSupplyArcs(arcs);
			// Resolve connected supplier features by id.
			const supplierIds = new Set(arcs.map((a) => a.properties.supplier_id));
			const suppliers = this.suppliers.filter(
				(s) => supplierIds.has(s.properties.id),
			);
			this._drawConnectedSuppliers(suppliers);
			const focusFeatures = [school, ...suppliers];
			this._drawSelectionLabels(focusFeatures);
			this._drawSelectedRing(school);
			this._fitBoundsTo(focusFeatures);
		},

		selectSupplier(supplier) {
			this.setAnalysisFocus("supplier", supplier);
			this._drawSelectedRing(supplier);
			const arcs = this.supplyChain.filter(
				(f) => f.properties.supplier_id === supplier.properties.id,
			);
			this.redrawSupplyArcs(arcs);
			const schoolIds = new Set(arcs.map((a) => a.properties.school_id));
			const schools = this.schools.filter(
				(s) => schoolIds.has(s.properties.id),
			);
			this._drawConnectedSuppliers([supplier]);
			const focusFeatures = [supplier, ...schools];
			this._drawSelectionLabels(focusFeatures);
			this._fitBoundsTo(focusFeatures);
		},

		selectIncident(incident) {
			this.setAnalysisFocus("incident", incident);
			// If incident has a primary school, ring it; else clear.
			const primarySchool = this.schools.find(
				(s) => s.properties.id === incident.school_id,
			);
			this._drawSelectedRing(primarySchool || null);
			const arcs = this.supplyChain.filter(
				(f) =>
					f.properties.supplier_id === incident.supplier_id &&
					incident.affected_school_ids.includes(f.properties.school_id),
			);
			this.redrawSupplyArcs(arcs);
			const affected = this.schools.filter(
				(f) => incident.affected_school_ids.includes(f.properties.id),
			);
			const supplier = this.suppliers.find(
				(s) => s.properties.id === incident.supplier_id,
			);
			this._drawConnectedSuppliers(supplier ? [supplier] : []);
			const focusFeatures = supplier ? [supplier, ...affected] : [...affected];
			this._drawSelectionLabels(focusFeatures);
			this._fitBoundsTo(focusFeatures);
		},

		selectRestaurant(restaurant) {
			this.selectedRestaurant = restaurant;
			this._drawSelectedRing(restaurant);
			const mapStore = useMapStore();
			const coord = restaurant?.geometry?.coordinates;
			if (mapStore.map && coord) {
				mapStore.easeToLocation([coord, 15, 0, 0]);
			}
		},

		// ── ArcLayer redraw (R2) ────────────────────────────────
		redrawSupplyArcs(filteredFeatures) {
			const mapStore = useMapStore();
			// Remove existing supply chain arc layer if any
			const existing = mapStore.currentLayers.filter(
				(l) => l.startsWith("fsm_supply_chain-"),
			);
			existing.forEach((l) => {
				const cfg = mapStore.mapConfigs[l];
				if (cfg) mapStore.removeMapLayer(cfg);
			});
			if (filteredFeatures.length === 0) return;
			// Re-add via mapStore.AddArcMapLayer
			const map_config = {
				index: "fsm_supply_chain",
				type: "arc",
				source: "geojson",
				city: mapStore.map?.style?.metadata?.city || "metrotaipei",
				layerId: "fsm_supply_chain-arc-metrotaipei",
				paint: {
					"arc-color": ["#FFA000", "#E53935"],
					"arc-width": 2,
					"arc-opacity": 0.7,
					"arc-animate": true,
				},
			};
			mapStore.step = 1;  // restart deck.gl arc animation from frame 1
			mapStore.AddArcMapLayer(
				map_config,
				{ type: "FeatureCollection", features: filteredFeatures },
			);
		},

		// Show text labels for the currently-clicked school/supplier and its
		// connected partners. Replaces existing label layer on each call. Pass
		// an empty array to clear.
		_drawSelectionLabels(features) {
			const mapStore = useMapStore();
			if (!mapStore.map) return;
			const sourceId = "fsm_selection_labels-source";
			const layerId = "fsm_selection_labels-layer";

			// Remove existing
			if (mapStore.map.getLayer(layerId)) {
				mapStore.map.removeLayer(layerId);
			}
			if (mapStore.map.getSource(sourceId)) {
				mapStore.map.removeSource(sourceId);
			}
			if (!features || features.length === 0) return;

			mapStore.map.addSource(sourceId, {
				type: "geojson",
				data: {
					type: "FeatureCollection",
					features: features,
				},
			});

			mapStore.map.addLayer({
				id: layerId,
				type: "symbol",
				source: sourceId,
				layout: {
					"text-field": ["get", "name"],
					"text-size": 11,
					"text-anchor": "top",
					"text-offset": [0, 1.0],
					"text-allow-overlap": false,
					"text-optional": true,
					"text-padding": 4,
				},
				paint: {
					"text-color": "#00E5FF",
					"text-halo-color": "#0A1228",
					"text-halo-width": 2,
					"text-halo-blur": 1,
				},
			});
		},

		// Color hint for a selected feature — matches the dot color so the
		// outer ring reads as "this point you picked", not a generic highlight.
		_featureColor(feature) {
			const p = feature?.properties || {};
			if (p.recent_alert === "red") return "#FF1744";
			if (p.recent_alert === "normal") return "#0288D1";
			const hl = p.hazard_level;
			if (hl === "critical") return "#FF1744";
			if (hl === "high") return "#FF6D00";
			if (hl === "medium") return "#FFC107";
			if (hl === "low") return "#00E676";
			if (hl === "info") return "#00E5FF";
			return "#00E5FF";
		},

		// Show an extra outer ring around any selected feature (school /
		// supplier / restaurant). Stroke color matches the feature's dot color.
		// Pass null/undefined to clear.
		_drawSelectedRing(feature) {
			const mapStore = useMapStore();
			if (!mapStore.map) return;
			const sourceId = "fsm_selected-source";
			const layerId = "fsm_selected-layer";

			if (mapStore.map.getLayer(layerId)) {
				mapStore.map.removeLayer(layerId);
			}
			if (mapStore.map.getSource(sourceId)) {
				mapStore.map.removeSource(sourceId);
			}
			if (!feature) return;

			mapStore.map.addSource(sourceId, {
				type: "geojson",
				data: { type: "FeatureCollection", features: [feature] },
			});

			mapStore.map.addLayer({
				id: layerId,
				type: "circle",
				source: sourceId,
				paint: {
					"circle-color": "rgba(0,0,0,0)",
					"circle-radius": 13,
					"circle-stroke-width": 2.5,
					"circle-stroke-color": this._featureColor(feature),
					"circle-stroke-opacity": 1,
				},
			});
		},

		// Programmatic temporary layer that shows ONLY the suppliers connected
		// to the currently-clicked school/supplier/incident, with neon-glow
		// styling matching the school dots. Pass empty array to clear.
		_drawConnectedSuppliers(supplierFeatures) {
			const mapStore = useMapStore();
			if (!mapStore.map) return;
			this._ensureTruckImage();
			const sourceId = "fsm_connected_suppliers-source";
			const haloLayerId = "fsm_connected_suppliers-halo";
			const truckLayerId = "fsm_connected_suppliers-truck";

			// Remove existing
			[truckLayerId, haloLayerId].forEach((id) => {
				if (mapStore.map.getLayer(id)) mapStore.map.removeLayer(id);
			});
			if (mapStore.map.getSource(sourceId)) mapStore.map.removeSource(sourceId);
			if (!supplierFeatures || supplierFeatures.length === 0) return;

			mapStore.map.addSource(sourceId, {
				type: "geojson",
				data: {
					type: "FeatureCollection",
					features: supplierFeatures,
				},
			});

			// Halo glow layer (blurred circle behind truck)
			mapStore.map.addLayer({
				id: haloLayerId,
				type: "circle",
				source: sourceId,
				paint: {
					"circle-color": ["match", ["get", "recent_alert"], "red", "#FF1744", "#00E5FF"],
					"circle-radius": 13,
					"circle-opacity": 0.25,
					"circle-blur": 0.7,
				},
			});

			// Truck icon (SDF, tinted)
			mapStore.map.addLayer({
				id: truckLayerId,
				type: "symbol",
				source: sourceId,
				layout: {
					"icon-image": "fsm-truck",
					"icon-size": 0.7,
					"icon-allow-overlap": true,
					"icon-ignore-placement": true,
				},
				paint: {
					"icon-color": ["match", ["get", "recent_alert"], "red", "#FF1744", "#00E5FF"],
				},
			});

			// Click handler — register once. Use the truck layer for hit-testing.
			if (!this._supplierClickAttached) {
				mapStore.map.on("click", truckLayerId, (e) => {
					const f = e.features?.[0];
					if (!f) return;
					this.selectSupplier(f);
				});
				mapStore.map.on("mouseenter", truckLayerId, () => {
					mapStore.map.getCanvas().style.cursor = "pointer";
				});
				mapStore.map.on("mouseleave", truckLayerId, () => {
					mapStore.map.getCanvas().style.cursor = "";
				});
				this._supplierClickAttached = true;
			}
		},

		_fitBoundsTo(features) {
			const mapStore = useMapStore();
			if (!mapStore.map || !features || features.length === 0) return;
			if (features.length === 1) {
				const [lng, lat] = features[0].geometry.coordinates;
				mapStore.easeToLocation([[lng, lat], 14, 0, 0]);
				return;
			}
			const lats = features.map((f) => f.geometry.coordinates[1]);
			const lngs = features.map((f) => f.geometry.coordinates[0]);
			const bounds = [
				[Math.min(...lngs), Math.min(...lats)],
				[Math.max(...lngs), Math.max(...lats)],
			];
			mapStore.map.fitBounds(bounds, {
				padding: { top: 80, right: 420, bottom: 80, left: 240 },
				maxZoom: 14,
				duration: 600,
			});
		},

		// ── Reset on dashboard exit ─────────────────────────────
		resetAll() {
			const mapStore = useMapStore();
			// Remove selection labels (created by _drawSelectionLabels)
			if (mapStore.map) {
				if (mapStore.map.getLayer("fsm_selection_labels-layer")) {
					mapStore.map.removeLayer("fsm_selection_labels-layer");
				}
				if (mapStore.map.getSource("fsm_selection_labels-source")) {
					mapStore.map.removeSource("fsm_selection_labels-source");
				}
				if (mapStore.map.getLayer("fsm_selected-layer")) {
					mapStore.map.removeLayer("fsm_selected-layer");
				}
				if (mapStore.map.getSource("fsm_selected-source")) {
					mapStore.map.removeSource("fsm_selected-source");
				}
				["fsm_connected_suppliers-truck", "fsm_connected_suppliers-halo"].forEach((id) => {
					if (mapStore.map.getLayer(id)) mapStore.map.removeLayer(id);
				});
				if (mapStore.map.getSource("fsm_connected_suppliers-source")) {
					mapStore.map.removeSource("fsm_connected_suppliers-source");
				}
			}
			// Defensive removal of any fsm_* layers
			["fsm_schools", "fsm_supply_chain", "fsm_suppliers", "fsm_supplier_dots", "fsm_restaurants", "fsm_district_heat"]
				.forEach((idx) => {
					const matching = mapStore.currentLayers.filter(
						(l) => l.startsWith(`${idx}-`),
					);
					matching.forEach((l) => {
						const cfg = mapStore.mapConfigs[l];
						if (cfg) mapStore.removeMapLayer(cfg);
					});
				});
			this.$reset();
		},
	},
});
