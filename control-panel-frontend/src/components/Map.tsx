import { useState, useRef, useCallback } from 'react';
import { Map as MapGL } from 'react-map-gl/maplibre';
import type { MapRef } from 'react-map-gl/maplibre';
import DeckGL from '@deck.gl/react';
import type { Layer } from '@deck.gl/core';
import type { PickingInfo } from '@deck.gl/core';
import 'maplibre-gl/dist/maplibre-gl.css';
import styles from './Map.module.css';
import type { InspectedEntity } from './InspectorPopup';

interface MapProps {
  layers?: Layer[];
  onEntityClick?: (entity: InspectedEntity, x: number, y: number) => void;
}

interface ViewState {
  latitude: number;
  longitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
}

export default function Map({ layers = [], onEntityClick }: MapProps) {
  const mapRef = useRef<MapRef>(null);
  const [viewState, setViewState] = useState<ViewState>({
    latitude: -23.55,
    longitude: -46.63,
    zoom: 11,
    pitch: 0,
    bearing: 0,
  });

  const handleWebGLError = useCallback((error: Error) => {
    console.error('DeckGL WebGL error:', error);
    // Re-throw to trigger error boundary
    throw error;
  }, []);

  const handleClick = useCallback(
    (info: PickingInfo) => {
      if (!onEntityClick) return;

      if (info.object) {
        const { object, layer } = info;

        if (layer && layer.id === 'zones') {
          onEntityClick({ type: 'zone', data: object }, info.x, info.y);
        } else if (layer && layer.id === 'drivers') {
          onEntityClick({ type: 'driver', data: object }, info.x, info.y);
        } else if (layer && layer.id === 'riders') {
          onEntityClick({ type: 'rider', data: object }, info.x, info.y);
        }
      }
    },
    [onEntityClick]
  );

  return (
    <div className={styles['map-container']}>
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState: newViewState }) => setViewState(newViewState as ViewState)}
        layers={layers}
        controller={true}
        onError={handleWebGLError}
        onClick={handleClick}
      >
        <MapGL
          ref={mapRef}
          mapStyle="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
          attributionControl={true}
        />
      </DeckGL>
    </div>
  );
}
