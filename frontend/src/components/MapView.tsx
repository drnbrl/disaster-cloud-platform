import { useEffect, useRef } from "react";
import maplibregl, { type StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { DisasterRequest } from "../types";

const remoteStyle: StyleSpecification = {
  version: 8,
  sources: { osm: { type: "raster", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256, attribution: "© OpenStreetMap contributors" } },
  layers: [{ id: "osm", type: "raster", source: "osm" }]
};

const localStyle: StyleSpecification = {
  version: 8,
  sources: {
    "openstreetmap-tiles": {
      type: "raster",
      tiles: [
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      ],
      tileSize: 256,
      minzoom: 0,
      maxzoom: 19,
      attribution: "© OpenStreetMap contributors"
    }
  },
  layers: [
    {
      id: "openstreetmap-layer",
      type: "raster",
      source: "openstreetmap-tiles"
    }
  ]
};

const style = import.meta.env.VITE_AUTH_MODE === "local" ? localStyle : remoteStyle;

export function MapView({ requests }: { requests: DisasterRequest[] }) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!ref.current) return;
    const map = new maplibregl.Map({ container: ref.current, style, center: [35.2, 38.5], zoom: 4.6 });
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    const markers: maplibregl.Marker[] = [];
    for (const request of requests) {
      if (!hasValidCoordinates(request)) continue;
      const element = document.createElement("button");
      element.className = `map-marker marker-${request.priorityLevel ?? "pending"}`;
      element.title = `${request.city}: ${request.priorityLevel ?? "bekleniyor"}`;
      const popupText = [
        request.city,
        `Puan: ${request.priorityScore ?? "-"}`,
        `Kişi: ${request.peopleCount ?? "-"}`,
        locationLabel(request)
      ].filter(Boolean).join(" | ");
      const popup = new maplibregl.Popup({ offset: 18 }).setText(popupText);
      markers.push(new maplibregl.Marker({ element }).setLngLat([request.longitude, request.latitude]).setPopup(popup).addTo(map));
    }
    return () => { markers.forEach(marker => marker.remove()); map.remove(); };
  }, [requests]);
  return <div className="map" ref={ref} aria-label="Afet talepleri haritası" />;
}

function hasValidCoordinates(request: DisasterRequest): request is DisasterRequest & { latitude: number; longitude: number } {
  return (
    typeof request.latitude === "number"
    && Number.isFinite(request.latitude)
    && request.latitude >= -90
    && request.latitude <= 90
    && typeof request.longitude === "number"
    && Number.isFinite(request.longitude)
    && request.longitude >= -180
    && request.longitude <= 180
  );
}

function locationLabel(request: DisasterRequest): string | undefined {
  if (request.locationSource === "USER_COORDINATES") return "Konum: Kullanıcı koordinatı";
  if (request.locationSource === "GEOCODED_ADDRESS") return "Konum: Adresten yaklaşık olarak belirlendi";
  return undefined;
}
