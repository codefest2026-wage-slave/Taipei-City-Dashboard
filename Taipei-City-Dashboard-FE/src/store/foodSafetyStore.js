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

		// Sub-toggles for school map (LayerToggle.vue)
		layerToggles: {
			showSchools: true,
			showSuppliers: false,
		},

		// Single covering analysis focus (covers school | supplier | incident)
		analysisFocus: null,          // { type, payload } | null

		// Restaurant selection (independent panel)
		selectedRestaurant: null,

		// School map UX
		schoolSearchQuery: "",

		// Restaurant map UX
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

		// Loading flags
		loading: {
			schools: false, suppliers: false, supplyChain: false,
			incidents: false, districtHeatmap: false,
			restaurants: false, restaurantInspections: false,
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
		// Recent N incidents sorted by date desc (RecentIncidentsStrip)
		recentIncidents(state) {
			return [...state.incidents].sort(
				(a, b) => b.occurred_at.localeCompare(a.occurred_at),
			);
		},
		// Stats for ExternalStatsStrip (校外底部 4 張卡)
		externalStats(state) {
			const total = state.restaurants.length;
			const fail = state.restaurants.filter(
				(f) => f.properties.risk_quadrant === "high_risk"
				    || f.properties.risk_quadrant === "emerging",
			).length;
			const failRate = total > 0 ? (fail / total * 100).toFixed(2) : "0.00";
			const highRiskDistricts = new Set(
				state.restaurants
					.filter((f) => f.properties.risk_quadrant === "high_risk")
					.map((f) => f.properties.district),
			).size;
			return { total, fail, failRate, highRiskDistricts };
		},
	},

	actions: {
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
			this.schools = schools.features;
			this.suppliers = suppliers.features;
			this.supplyChain = chain.features;
			this.incidents = incidents;
			this.districtHeatmap = heat;
			this.restaurants = rest.features;
			this.restaurantInspections = insp;
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

		applyCityFilter(city) {
			// city: 'metrotaipei' | 'taipei' | 'ntpc'
			const mapStore = useMapStore();
			const cityFilter =
				city === "taipei" ? ["==", ["get", "city"], "臺北市"] :
					city === "ntpc"   ? ["==", ["get", "city"], "新北市"] :
						null;
			["fsm_schools", "fsm_restaurants"].forEach((idx) => {
				const layer = mapStore.currentLayers.find((l) => l.startsWith(`${idx}-`));
				if (!layer || !mapStore.map?.getLayer(layer)) return;
				if (cityFilter) mapStore.map.setFilter(layer, cityFilter);
				else            mapStore.map.setFilter(layer, null);
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
			// Severity: 'all' | 'high' | 'medium' | 'low'
			if (f.severity !== "all") {
				conditions.push(["==", ["get", "severity"], f.severity]);
			}
			// timeRange currently has no per-feature property to filter on — mock data
			// has no inspection_date per feature; the filter is captured in state for
			// future use but does not currently constrain the layer. Spec §4.2 has no
			// such field on restaurants.geojson; would require joining to inspections.
			const expr =
				conditions.length === 0 ? null :
					conditions.length === 1 ? conditions[0] :
						["all", ...conditions];
			mapStore.map.setFilter(layer, expr);
		},

		_removeLayerGroup(layer, mapStore) {
			const ids =
				layer === "school"
					? ["fsm_schools", "fsm_supply_chain", "fsm_suppliers"]
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
			const mapStore = useMapStore();
			this.setAnalysisFocus("school", school);
			const [lng, lat] = school.geometry.coordinates;
			mapStore.easeToLocation([[lng, lat], 14, 0, 0]);
			// Always draw the school's supply arcs on click — this is the
			// path-1 behavior in spec §5.2.1.
			const arcs = this.supplyChain.filter(
				(f) => f.properties.school_id === school.properties.id,
			);
			this.redrawSupplyArcs(arcs);
		},

		selectSupplier(supplier) {
			this.setAnalysisFocus("supplier", supplier);
			const arcs = this.supplyChain.filter(
				(f) => f.properties.supplier_id === supplier.properties.id,
			);
			this.redrawSupplyArcs(arcs);
		},

		selectIncident(incident) {
			const mapStore = useMapStore();
			this.setAnalysisFocus("incident", incident);
			// Highlight all affected schools by drawing arcs from supplier → schools
			const arcs = this.supplyChain.filter(
				(f) =>
					f.properties.supplier_id === incident.supplier_id &&
					incident.affected_school_ids.includes(f.properties.school_id),
			);
			this.redrawSupplyArcs(arcs);
			// Fit bounds to affected schools
			const affected = this.schools.filter(
				(f) => incident.affected_school_ids.includes(f.properties.id),
			);
			if (affected.length === 0) return;
			const lats = affected.map((f) => f.geometry.coordinates[1]);
			const lngs = affected.map((f) => f.geometry.coordinates[0]);
			const center = [
				(Math.min(...lngs) + Math.max(...lngs)) / 2,
				(Math.min(...lats) + Math.max(...lats)) / 2,
			];
			mapStore.easeToLocation([center, 12, 0, 0]);
		},

		selectRestaurant(restaurant) {
			this.selectedRestaurant = restaurant;
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
				layerId: `fsm_supply_chain-arc-${Date.now()}`,
				paint: {
					"arc-color": ["#FFA000", "#E53935"],
					"arc-width": 2,
					"arc-opacity": 0.7,
					"arc-animate": true,
				},
			};
			mapStore.AddArcMapLayer(
				map_config,
				{ type: "FeatureCollection", features: filteredFeatures },
			);
		},

		// ── Layer toggles within school map ─────────────────────
		toggleSubLayer(name) {
			this.layerToggles[name] = !this.layerToggles[name];
			const mapStore = useMapStore();
			if (!mapStore.map) return;
			const prefix = name === "showSchools" ? "fsm_schools-" : "fsm_suppliers-";
			const visible = this.layerToggles[name] ? "visible" : "none";
			mapStore.currentLayers
				.filter((l) => l.startsWith(prefix))
				.forEach((l) => {
					if (mapStore.map.getLayer(l)) {
						mapStore.map.setLayoutProperty(l, "visibility", visible);
					}
				});
			// If suppliers just turned OFF and we have a focused school, keep its
			// supplier connections visible (per spec: click-school always shows
			// connected suppliers via arcs even when global toggle is off).
			// Nothing extra needed here — arcs are drawn separately by selectSchool.
		},

		// ── Reset on dashboard exit ─────────────────────────────
		resetAll() {
			const mapStore = useMapStore();
			// Defensive removal of any fsm_* layers
			["fsm_schools", "fsm_supply_chain", "fsm_suppliers", "fsm_restaurants", "fsm_district_heat"]
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
