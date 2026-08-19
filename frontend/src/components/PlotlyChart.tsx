"use client";

import dynamic from "next/dynamic";

// Plotly must be loaded client-side only (it references `window`).
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

export default function PlotlyChart(props: any) {
  return <Plot {...props} config={{ displayModeBar: false, responsive: true }} style={{ width: "100%", height: "100%" }} useResizeHandler />;
}
