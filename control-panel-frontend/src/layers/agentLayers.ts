import { ScatterplotLayer, PathLayer } from '@deck.gl/layers';
import { TripsLayer } from '@deck.gl/geo-layers';
import type { Driver, Rider, Trip, GPSTrail } from '../types/api';

export const DRIVER_COLORS = {
  online: [0, 255, 0] as [number, number, number],
  busy: [0, 0, 255] as [number, number, number],
  offline: [128, 128, 128] as [number, number, number],
  en_route: [0, 0, 255] as [number, number, number],
};

export const RIDER_COLORS = {
  waiting: [255, 165, 0] as [number, number, number],
  in_transit: [128, 0, 128] as [number, number, number],
};

export function createOnlineDriversLayer(drivers: Driver[]) {
  const onlineDrivers = drivers.filter((d) => d.status === 'online');
  return new ScatterplotLayer({
    id: 'online-drivers',
    data: onlineDrivers,
    pickable: true,
    radiusMinPixels: 3,
    radiusMaxPixels: 10,
    getPosition: (d: Driver) => [d.longitude, d.latitude],
    getRadius: 50,
    getFillColor: DRIVER_COLORS.online,
  });
}

export function createOfflineDriversLayer(drivers: Driver[]) {
  const offlineDrivers = drivers.filter((d) => d.status === 'offline');
  return new ScatterplotLayer({
    id: 'offline-drivers',
    data: offlineDrivers,
    pickable: true,
    radiusMinPixels: 3,
    radiusMaxPixels: 10,
    getPosition: (d: Driver) => [d.longitude, d.latitude],
    getRadius: 50,
    getFillColor: DRIVER_COLORS.offline,
  });
}

export function createBusyDriversLayer(drivers: Driver[]) {
  const busyDrivers = drivers.filter((d) => d.status === 'busy' || d.status === 'en_route');
  return new ScatterplotLayer({
    id: 'busy-drivers',
    data: busyDrivers,
    pickable: true,
    radiusMinPixels: 3,
    radiusMaxPixels: 10,
    getPosition: (d: Driver) => [d.longitude, d.latitude],
    getRadius: 50,
    getFillColor: DRIVER_COLORS.busy,
  });
}

export function createWaitingRidersLayer(riders: Rider[]) {
  const waitingRiders = riders.filter((r) => r.status === 'waiting');
  return new ScatterplotLayer({
    id: 'waiting-riders',
    data: waitingRiders,
    pickable: true,
    radiusMinPixels: 3,
    radiusMaxPixels: 10,
    getPosition: (d: Rider) => [d.longitude, d.latitude],
    getRadius: 50,
    getFillColor: RIDER_COLORS.waiting,
  });
}

export function createInTransitRidersLayer(riders: Rider[]) {
  const inTransitRiders = riders.filter((r) => r.status === 'in_transit');
  return new ScatterplotLayer({
    id: 'in-transit-riders',
    data: inTransitRiders,
    pickable: true,
    radiusMinPixels: 3,
    radiusMaxPixels: 10,
    getPosition: (d: Rider) => [d.longitude, d.latitude],
    getRadius: 50,
    getFillColor: RIDER_COLORS.in_transit,
  });
}

export function createTripsLayer(trails: GPSTrail[], currentTime: number, visible: boolean = true) {
  return new TripsLayer({
    id: 'gps-trails',
    data: trails,
    visible,
    getPath: (d: GPSTrail) => d.path,
    getTimestamps: (d: GPSTrail) => d.path.map((p) => p[2]),
    trailLength: 300,
    currentTime,
    widthMinPixels: 2,
    getColor: [255, 100, 100],
  });
}

export function createPathLayer(trips: Trip[], visible: boolean = true) {
  return new PathLayer({
    id: 'trip-routes',
    data: trips,
    visible,
    pickable: true,
    getPath: (d: Trip) => d.route,
    getColor: [0, 200, 255],
    getWidth: 100,
    widthMinPixels: 2,
  });
}

export function createDriverLayer(drivers: Driver[]) {
  return new ScatterplotLayer({
    id: 'drivers',
    data: drivers,
    pickable: true,
    radiusMinPixels: 3,
    radiusMaxPixels: 10,
    getPosition: (d: Driver) => [d.longitude, d.latitude],
    getRadius: 50,
    getFillColor: (d: Driver) => DRIVER_COLORS[d.status],
    updateTriggers: {
      getFillColor: [drivers.map((d) => d.status)],
    },
  });
}

export function createRiderLayer(riders: Rider[]) {
  return new ScatterplotLayer({
    id: 'riders',
    data: riders,
    pickable: true,
    radiusMinPixels: 3,
    radiusMaxPixels: 10,
    getPosition: (d: Rider) => [d.longitude, d.latitude],
    getRadius: 50,
    getFillColor: (d: Rider) => RIDER_COLORS[d.status],
    updateTriggers: {
      getFillColor: [riders.map((r) => r.status)],
    },
  });
}
