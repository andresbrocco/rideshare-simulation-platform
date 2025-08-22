import { useState, useRef } from 'react';
import { Map as MapGL } from 'react-map-gl/maplibre';
import type { MapRef } from 'react-map-gl/maplibre';
import DeckGL from '@deck.gl/react';
import type { Layer } from '@deck.gl/core';
import 'maplibre-gl/dist/maplibre-gl.css';
import styles from './Map.module.css';

interface MapProps {
  layers?: Layer[];
}

interface ViewState {
  latitude: number;
  longitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
}

export default function Map({ layers = [] }: MapProps) {
  const mapRef = useRef<MapRef>(null);
  const [viewState, setViewState] = useState<ViewState>({
    latitude: -23.55,
    longitude: -46.63,
    zoom: 11,
    pitch: 0,
    bearing: 0,
  });

  return (
    <div className={styles['map-container']}>
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState: newViewState }) => setViewState(newViewState as ViewState)}
        layers={layers}
        controller={true}
      >
        <MapGL
          ref={mapRef}
          mapStyle="https://demotiles.maplibre.org/style.json"
          attributionControl={true}
        />
      </DeckGL>
    </div>
  );
}
