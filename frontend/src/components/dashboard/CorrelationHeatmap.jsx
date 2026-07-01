import { useMemo } from 'react';
import Plot from 'react-plotly.js';
import { GitBranch } from 'lucide-react';

const ASSETS = ['NIFTY', 'S&P 500', 'BTC', 'Gold', 'Crude', 'DXY', 'EUR/USD'];

function generateCorrelationMatrix() {
  // Realistic correlation values
  const raw = [
    // NIFTY   S&P500  BTC     Gold    Crude   DXY     EUR/USD
    [1.00,    0.72,   0.35,   0.18,   0.42,  -0.31,   0.28],  // NIFTY
    [0.72,    1.00,   0.42,   0.12,   0.38,  -0.45,   0.41],  // S&P 500
    [0.35,    0.42,   1.00,  -0.08,   0.22,  -0.38,   0.33],  // BTC
    [0.18,    0.12,  -0.08,   1.00,   0.25,  -0.62,   0.58],  // Gold
    [0.42,    0.38,   0.22,   0.25,   1.00,  -0.18,   0.15],  // Crude
    [-0.31,  -0.45,  -0.38,  -0.62,  -0.18,   1.00,  -0.88],  // DXY
    [0.28,    0.41,   0.33,   0.58,   0.15,  -0.88,   1.00],  // EUR/USD
  ];
  return raw;
}

export default function CorrelationHeatmap({ className = '' }) {
  const matrix = useMemo(() => generateCorrelationMatrix(), []);

  // Text annotations
  const annotationText = matrix.map(row => row.map(v => v.toFixed(2)));

  return (
    <div className={`glass-card p-5 ${className}`}>
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-subtle">
          <GitBranch className="h-4.5 w-4.5 text-accent" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-text-primary">Correlation Matrix</h3>
          <p className="text-xs text-text-secondary">Cross-asset correlation heatmap</p>
        </div>
      </div>

      {/* Plotly Heatmap */}
      <div className="w-full" style={{ minHeight: 380 }}>
        <Plot
          data={[
            {
              z: matrix,
              x: ASSETS,
              y: ASSETS,
              type: 'heatmap',
              colorscale: [
                [0, '#1f6feb'],      // deep blue at -1
                [0.25, '#58a6ff'],   // lighter blue
                [0.5, '#161b22'],    // dark center at 0
                [0.75, '#f85149'],   // lighter red
                [1, '#da3633'],      // deep red at +1
              ],
              zmin: -1,
              zmax: 1,
              text: annotationText,
              texttemplate: '%{text}',
              textfont: {
                family: 'JetBrains Mono, monospace',
                size: 12,
                color: '#e6edf3',
              },
              hovertemplate:
                '<b>%{y}</b> vs <b>%{x}</b><br>' +
                'Correlation: <b>%{z:.2f}</b>' +
                '<extra></extra>',
              showscale: true,
              colorbar: {
                thickness: 12,
                len: 0.85,
                outlinewidth: 0,
                tickfont: {
                  family: 'JetBrains Mono, monospace',
                  size: 10,
                  color: '#8b949e',
                },
                tickvals: [-1, -0.5, 0, 0.5, 1],
                title: {
                  text: 'ρ',
                  font: {
                    family: 'Inter, sans-serif',
                    size: 12,
                    color: '#8b949e',
                  },
                  side: 'right',
                },
              },
              xgap: 2,
              ygap: 2,
            },
          ]}
          layout={{
            autosize: true,
            height: 380,
            margin: { l: 80, r: 60, t: 10, b: 60 },
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            font: {
              family: 'Inter, sans-serif',
              color: '#8b949e',
            },
            xaxis: {
              side: 'bottom',
              tickangle: -35,
              tickfont: {
                family: 'Inter, sans-serif',
                size: 11,
                color: '#8b949e',
              },
              showgrid: false,
              zeroline: false,
            },
            yaxis: {
              autorange: 'reversed',
              tickfont: {
                family: 'Inter, sans-serif',
                size: 11,
                color: '#8b949e',
              },
              showgrid: false,
              zeroline: false,
            },
            hoverlabel: {
              bgcolor: '#161b22',
              bordercolor: '#30363d',
              font: {
                family: 'Inter, sans-serif',
                size: 12,
                color: '#e6edf3',
              },
            },
          }}
          config={{
            displayModeBar: false,
            responsive: true,
            staticPlot: false,
          }}
          style={{ width: '100%', height: '100%' }}
          useResizeHandler={true}
        />
      </div>

      {/* Legend footer */}
      <div className="flex items-center justify-center gap-2 mt-2">
        <span className="text-[10px] text-accent font-medium">-1 (Inverse)</span>
        <div className="flex gap-0.5">
          {['#1f6feb', '#58a6ff', '#2d333b', '#f85149', '#da3633'].map((c, i) => (
            <div key={i} className="w-6 h-2.5 rounded-sm" style={{ backgroundColor: c }} />
          ))}
        </div>
        <span className="text-[10px] text-negative font-medium">+1 (Correlated)</span>
      </div>
    </div>
  );
}
