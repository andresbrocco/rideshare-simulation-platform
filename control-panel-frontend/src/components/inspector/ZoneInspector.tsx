import type { ZoneData } from '../../types/api';
import { InspectorRow } from './InspectorRow';

interface ZoneInspectorProps {
  zone: ZoneData;
}

export function ZoneInspector({ zone }: ZoneInspectorProps) {
  return (
    <>
      <h3>Zone</h3>
      <InspectorRow label="Name" value={zone.feature.properties.name} />
      <InspectorRow label="Surge Multiplier" value={`${zone.surge}x`} />
      <InspectorRow label="Drivers" value={zone.driver_count} />
    </>
  );
}
