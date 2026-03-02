declare module 'react-simple-maps' {
  import { Component, ReactNode } from 'react';

  export interface ComposableMapProps {
    projection?: string;
    projectionConfig?: {
      scale?: number;
      center?: [number, number];
    };
    width?: number;
    height?: number;
    style?: React.CSSProperties;
    zoom?: number;
    children?: ReactNode;
  }

  export interface GeographiesProps {
    geography: string | Record<string, unknown>;
    children: (args: { geographies: Geography[] }) => ReactNode;
  }

  export interface Geography {
    rsmKey: string;
    properties: Record<string, unknown>;
    geometry: unknown;
  }

  export interface GeographyProps {
    key?: string;
    geography: Geography;
    fill?: string;
    stroke?: string;
    strokeWidth?: number | string;
    style?: {
      default?: Record<string, unknown>;
      hover?: Record<string, unknown>;
      pressed?: Record<string, unknown>;
    };
    children?: ReactNode;
  }

  export interface MarkerProps {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    coordinates: any;
    children?: ReactNode;
    key?: string;
  }

  export class ComposableMap extends Component<ComposableMapProps> {}
  export class Geographies extends Component<GeographiesProps> {}
  export class Geography extends Component<GeographyProps> {}
  export class Marker extends Component<MarkerProps> {}
}
