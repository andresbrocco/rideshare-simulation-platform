import { useState, useRef, useCallback, useEffect } from 'react';
import { Map as MapGL } from 'react-map-gl/maplibre';
import type { MapRef } from 'react-map-gl/maplibre';
import DeckGL from '@deck.gl/react';
import type { Deck, Layer } from '@deck.gl/core';
import type { PickingInfo } from '@deck.gl/core';
import 'maplibre-gl/dist/maplibre-gl.css';
import styles from './Map.module.css';
import type { InspectedEntity } from './InspectorPopup';
import type { Driver, Rider } from '../types/api';
import type { PlacementMode } from '../constants/dnaPresets';

interface MapProps {
  layers?: Layer[];
  onEntityClick?: (entity: InspectedEntity, x: number, y: number) => void;
  placementMode?: PlacementMode | null;
  onPlacement?: (lat: number, lng: number) => void;
  destinationMode?: boolean;
  onDestinationSelect?: (lat: number, lng: number) => void;
  onZoomChange?: (zoom: number) => void;
}

interface ViewState {
  latitude: number;
  longitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
}

function getLayerType(layerId: string): 'driver' | 'rider' | 'zone' | null {
  if (layerId === 'drivers' || layerId.endsWith('-drivers')) return 'driver';
  if (layerId === 'riders' || layerId.endsWith('-riders')) return 'rider';
  if (layerId === 'zones') return 'zone';
  return null;
}

export default function Map({
  layers = [],
  onEntityClick,
  placementMode,
  onPlacement,
  destinationMode,
  onDestinationSelect,
  onZoomChange,
}: MapProps) {
  const mapRef = useRef<MapRef>(null);
  const deckRef = useRef<Deck | null>(null);
  const [viewState, setViewState] = useState<ViewState>({
    latitude: -23.55,
    longitude: -46.63,
    zoom: 11,
    pitch: 0,
    bearing: 0,
  });
  const [isHoveringAgent, setIsHoveringAgent] = useState(false);

  // Cleanup DeckGL resources on unmount
  useEffect(() => {
    return () => {
      if (deckRef.current) {
        deckRef.current.finalize();
        deckRef.current = null;
      }
    };
  }, []);

  const handleDeckLoad = useCallback((deck: Deck) => {
    deckRef.current = deck;
  }, []);

  const handleWebGLError = useCallback((error: Error) => {
    console.error('DeckGL WebGL error:', error);
    throw error;
  }, []);

  const getCursor = useCallback(
    ({ isDragging }: { isDragging: boolean }) => {
      if (placementMode || destinationMode) {
        return 'crosshair';
      }
      if (isDragging) {
        return 'grabbing';
      }
      if (isHoveringAgent) {
        return 'pointer';
      }
      return 'grab';
    },
    [placementMode, destinationMode, isHoveringAgent]
  );

  const handleHover = useCallback((info: PickingInfo) => {
    if (info.object && info.layer) {
      const type = getLayerType(info.layer.id);
      setIsHoveringAgent(type === 'driver' || type === 'rider');
    } else {
      setIsHoveringAgent(false);
    }
  }, []);

  const handleClick = useCallback(
    (info: PickingInfo) => {
      // Handle destination selection mode first (highest priority)
      if (destinationMode && onDestinationSelect && info.coordinate) {
        const [clickLng, clickLat] = info.coordinate;
        onDestinationSelect(clickLat, clickLng);
        return;
      }

      // Handle placement mode
      if (placementMode && onPlacement && info.coordinate) {
        const [clickLng, clickLat] = info.coordinate;
        onPlacement(clickLat, clickLng);
        return;
      }

      if (!onEntityClick) return;

      // Use deck.gl's native picking - respects pixel-accurate hit detection
      if (info.object && info.layer) {
        const type = getLayerType(info.layer.id);
        if (type === 'driver') {
          onEntityClick({ type: 'driver', data: info.object as Driver }, info.x, info.y);
          return;
        }
        if (type === 'rider') {
          onEntityClick({ type: 'rider', data: info.object as Rider }, info.x, info.y);
          return;
        }
        if (type === 'zone') {
          onEntityClick({ type: 'zone', data: info.object }, info.x, info.y);
        }
      }
    },
    [onEntityClick, placementMode, onPlacement, destinationMode, onDestinationSelect]
  );

  return (
    <div className={styles['map-container']}>
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState: newViewState }) => {
          const vs = newViewState as ViewState;
          setViewState(vs);
          onZoomChange?.(vs.zoom);
        }}
        layers={layers}
        controller={true}
        onError={handleWebGLError}
        onClick={handleClick}
        onHover={handleHover}
        getCursor={getCursor}
        onLoad={handleDeckLoad}
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
