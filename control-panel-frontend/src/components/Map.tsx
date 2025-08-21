import { useState } from 'react';
import Map from 'react-map-gl/maplibre';
import DeckGL from '@deck.gl/react';
import type { ViewState } from '../types/simulation';

const INITIAL_VIEW_STATE: ViewState = {
  longitude: -46.6333,
  latitude: -23.5505,
  zoom: 11,
  pitch: 0,
  bearing: 0,
};

export default function MapView() {
  const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);

  return (
    <DeckGL
      viewState={viewState}
      onViewStateChange={({ viewState }) => setViewState(viewState as ViewState)}
      controller={true}
      layers={[]}
      style={{ position: 'relative', width: '100%', height: '100vh' }}
    >
      <Map mapStyle="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json" />
    </DeckGL>
  );
}
