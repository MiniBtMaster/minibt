import { LineStyle } from "lightweight-charts";


export interface DrawingOptions {
    lineColor: string;
    lineStyle: LineStyle
    width: number;
    /** Optional label text (shown in-pane and/or on the price axis). */
    text?: string;
    /** Draw `text` inside the pane, pinned to the left edge of the visible range. */
    labelVisible?: boolean;
    /** Draw `text` on the price (Y) axis. */
    axisLabelVisible?: boolean;
    /** Background of the in-pane label (falls back to `lineColor`). */
    labelBackgroundColor?: string;
    /** Text color of the in-pane label (falls back to white). */
    labelTextColor?: string;
    /** Font of the in-pane label (falls back to `12px sans-serif`). */
    labelFont?: string;
}

export const defaultOptions: DrawingOptions = {
    lineColor: '#1E80F0',
    lineStyle: LineStyle.Solid,
    width: 4,
    axisLabelVisible: true,
    labelVisible: false,
};
