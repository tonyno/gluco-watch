export interface GlucoseData {
  main: {
    glucose: number;
    timestamp: number;
    time: string;
  };
  fetched_at: string;
  fetched_at_unix: number;
  fetched_at_unix_ms: number;
}

export interface UserData {
  [key: string]: GlucoseData;
}
