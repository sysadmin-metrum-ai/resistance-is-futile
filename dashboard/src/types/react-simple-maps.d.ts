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
    style?: { [key: string]: React.CSSProperties };
    zoom?: number;
    children?: ReactNode;
  }

  export interface GeographiesProps {
    geography: string | object;
    children: (args: { geographies: Geography[] }) => ReactNode;
  }

  export interface Geography {
    rsmKey: string;
    properties: { [key: string]: any };
    geometry: any;
  }

  export interface GeographyProps {
    key?: string;
    geography: Geography;
    fill?: string;
    stroke?: string;
    strokeWidth?: number | string;
    style?: {
      default?: { [key: string]: any };
      hover?: { [key: string]: any };
      pressed?: { [key: string]: any };
    };
    children?: ReactNode;
  }

  export interface MarkerProps {
    coordinates: [number, number];
    children?: ReactNode;
    key?: string;
  }

  export class ComposableMap extends Component<ComposableMapProps> {}
  export class Geographies extends Component<GeographiesProps> {}
  export class Geography extends Component<GeographyProps> {}
  export class Marker extends Component<MarkerProps> {}
}
