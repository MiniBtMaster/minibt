import { DrawingTool, DrawingEventSource } from "../drawing/drawing-tool";
import { TrendLine } from "../trend-line/trend-line";
import { Box } from "../box/box";
import { Drawing } from "../drawing/drawing";
import { ContextMenu } from "../context-menu/context-menu";
import { GlobalParams } from "./global-params";
import { ISeriesApi, SeriesType } from "lightweight-charts";
import { HorizontalLine } from "../horizontal-line/horizontal-line";
import { RayLine } from "../horizontal-line/ray-line";
import { VerticalLine } from "../vertical-line/vertical-line";
import { FibonacciRetracement } from "../fibonacci/fibonacci";
import { Measure } from "../measure/measure";
import { ParallelChannel } from "../channel/channel";
import { Position } from "../position/position";
import { AndrewsPitchfork } from "../pitchfork/pitchfork";
import { Triangle } from "../triangle/triangle";
import { FibonacciExtension } from "../fib-extension/fibonacci-extension";
import { GannFan } from "../gann-fan/gann-fan";


interface Icon {
    div: HTMLDivElement,
    group: SVGGElement,
    type: new (...args: any[]) => Drawing
}

declare const window: GlobalParams

export class ToolBox {
    private static readonly TREND_SVG: string = '<rect x="3.84" y="13.67" transform="matrix(0.7071 -0.7071 0.7071 0.7071 -5.9847 14.4482)" width="21.21" height="1.56"/><path d="M23,3.17L20.17,6L23,8.83L25.83,6L23,3.17z M23,7.41L21.59,6L23,4.59L24.41,6L23,7.41z"/><path d="M6,20.17L3.17,23L6,25.83L8.83,23L6,20.17z M6,24.41L4.59,23L6,21.59L7.41,23L6,24.41z"/>';
    private static readonly HORZ_SVG: string = '<rect x="4" y="14" width="9" height="1"/><rect x="16" y="14" width="9" height="1"/><path d="M11.67,14.5l2.83,2.83l2.83-2.83l-2.83-2.83L11.67,14.5z M15.91,14.5l-1.41,1.41l-1.41-1.41l1.41-1.41L15.91,14.5z"/>';
    private static readonly RAY_SVG: string = '<rect x="8" y="14" width="17" height="1"/><path d="M3.67,14.5l2.83,2.83l2.83-2.83L6.5,11.67L3.67,14.5z M7.91,14.5L6.5,15.91L5.09,14.5l1.41-1.41L7.91,14.5z"/>';
    private static readonly BOX_SVG: string = '<rect x="8" y="6" width="12" height="1"/><rect x="9" y="22" width="11" height="1"/><path d="M3.67,6.5L6.5,9.33L9.33,6.5L6.5,3.67L3.67,6.5z M7.91,6.5L6.5,7.91L5.09,6.5L6.5,5.09L7.91,6.5z"/><path d="M19.67,6.5l2.83,2.83l2.83-2.83L22.5,3.67L19.67,6.5z M23.91,6.5L22.5,7.91L21.09,6.5l1.41-1.41L23.91,6.5z"/><path d="M19.67,22.5l2.83,2.83l2.83-2.83l-2.83-2.83L19.67,22.5z M23.91,22.5l-1.41,1.41l-1.41-1.41l1.41-1.41L23.91,22.5z"/><path d="M3.67,22.5l2.83,2.83l2.83-2.83L6.5,19.67L3.67,22.5z M7.91,22.5L6.5,23.91L5.09,22.5l1.41-1.41L7.91,22.5z"/><rect x="22" y="9" width="1" height="11"/><rect x="6" y="9" width="1" height="11"/>';
    private static readonly VERT_SVG: string = ToolBox.RAY_SVG;
    private static readonly FIB_SVG: string = '<rect x="4" y="7" width="20" height="1.5"/><rect x="4" y="14" width="20" height="1.5"/><rect x="4" y="21" width="20" height="1.5"/>';
    private static readonly MEASURE_SVG: string = '<path d="M4 20.5l16.5-16.5 1.5 1.5L5.5 22z"/><path d="M17 4h4v4l-2-2-2 2z"/>';
    private static readonly CHANNEL_SVG: string = '<path d="M3 17l14-14 2 2-14 14z"/><path d="M7 21l14-14 2 2-14 14z"/>';
    private static readonly POSITION_SVG: string = '<rect x="5" y="4" width="18" height="9"/><rect x="5" y="15" width="18" height="9"/>';
    private static readonly PITCHFORK_SVG: string = '<path d="M4 22 L24 4 l1.6 1.6 L6 24z"/><path d="M4 16 L20 2 l1.6 1.6 L6 18z"/><path d="M4 28 L28 6 l1.6 1.6 L6 30z"/>';
    private static readonly TRIANGLE_SVG: string = '<path d="M4 22 L14 5 L24 22 Z"/>';
    private static readonly FIB_EXT_SVG: string = '<rect x="4" y="6" width="20" height="1.5"/><rect x="4" y="13" width="20" height="1.5"/><rect x="4" y="20" width="20" height="1.5"/><path d="M4 4 L14 12 L4 26" fill="none" stroke="currentColor" stroke-width="1.5"/>';
    // 9 rays from a single point (the Gann angles 1x8 ... 8x1, with the 1x1 balance
    // line through the middle). Drawn with strokes, so each path needs
    // `stroke="currentColor"`: the toolbox colours its icons by setting `fill` on
    // the group, which on its own leaves a line-only icon completely blank.
    private static readonly GANN_SVG: string =
        '<circle cx="3" cy="26" r="1.7"/>' +
        '<path d="M3 26 L27 23" stroke="currentColor" stroke-width="0.9" fill="none"/>' +
        '<path d="M3 26 L27 20" stroke="currentColor" stroke-width="0.9" fill="none"/>' +
        '<path d="M3 26 L27 18" stroke="currentColor" stroke-width="0.9" fill="none"/>' +
        '<path d="M3 26 L27 14" stroke="currentColor" stroke-width="0.9" fill="none"/>' +
        '<path d="M3 26 L27 2" stroke="currentColor" stroke-width="1.5" fill="none"/>' +
        '<path d="M3 26 L16 1" stroke="currentColor" stroke-width="0.9" fill="none"/>' +
        '<path d="M3 26 L11 1" stroke="currentColor" stroke-width="0.9" fill="none"/>' +
        '<path d="M3 26 L9 1" stroke="currentColor" stroke-width="0.9" fill="none"/>' +
        '<path d="M3 26 L6 1" stroke="currentColor" stroke-width="0.9" fill="none"/>';

    div: HTMLDivElement;
    private activeIcon: Icon | null = null;

    private buttons: HTMLDivElement[] = [];

    private _commandFunctions: Function[];
    private _handlerID: string;

    private _drawingTool: DrawingTool;

    constructor(handlerID: string, source: DrawingEventSource, series: ISeriesApi<SeriesType>, commandFunctions: Function[]) {
        this._handlerID = handlerID;
        this._commandFunctions = commandFunctions;
        this._drawingTool = new DrawingTool(source, series,
                                            () => this.removeActiveAndSave(),
                                            () => this.saveDrawings());
        this.div = this._makeToolBox()
        new ContextMenu(this.saveDrawings, this._drawingTool);

        commandFunctions.push((event: KeyboardEvent) => {
            if ((event.metaKey || event.ctrlKey) && event.code === 'KeyZ') {
                // 不要先 pop：delete() 自己会从数组里移除、detach 并触发保存。
                // 以前这里先 pop 掉，delete() 就找不到它（idx == -1 直接返回），
                // 结果图形既不 detach（留在画布上）也不保存。
                const last = this._drawingTool.drawings[this._drawingTool.drawings.length - 1];
                this._drawingTool.delete(last ?? null);
                return true;
            }
            return false;
        });
    }

    toJSON() {
        // Exclude the chart attribute from serialization
        const { ...serialized} = this;
        return serialized;
    }

    private _makeToolBox() {
        let div = document.createElement('div')
        div.classList.add('toolbox');
        this.buttons.push(this._makeToolBoxElement(TrendLine, 'KeyT', ToolBox.TREND_SVG))
        this.buttons.push(this._makeToolBoxElement(HorizontalLine, 'KeyH', ToolBox.HORZ_SVG));
        this.buttons.push(this._makeToolBoxElement(RayLine, 'KeyR', ToolBox.RAY_SVG));
        this.buttons.push(this._makeToolBoxElement(Box, 'KeyB', ToolBox.BOX_SVG));
        this.buttons.push(this._makeToolBoxElement(VerticalLine, 'KeyV', ToolBox.VERT_SVG, true));
        this.buttons.push(this._makeToolBoxElement(FibonacciRetracement, 'KeyF', ToolBox.FIB_SVG));
        this.buttons.push(this._makeToolBoxElement(Measure, 'KeyM', ToolBox.MEASURE_SVG));
        this.buttons.push(this._makeToolBoxElement(ParallelChannel, 'KeyC', ToolBox.CHANNEL_SVG));
        this.buttons.push(this._makeToolBoxElement(Position, 'KeyP', ToolBox.POSITION_SVG));
        this.buttons.push(this._makeToolBoxElement(AndrewsPitchfork, 'KeyA', ToolBox.PITCHFORK_SVG));
        this.buttons.push(this._makeToolBoxElement(Triangle, 'KeyG', ToolBox.TRIANGLE_SVG));
        this.buttons.push(this._makeToolBoxElement(FibonacciExtension, 'KeyX', ToolBox.FIB_EXT_SVG));
        this.buttons.push(this._makeToolBoxElement(GannFan, 'KeyN', ToolBox.GANN_SVG));
        for (const button of this.buttons) {
            div.appendChild(button);
        }
        return div
    }

    private _makeToolBoxElement(DrawingType: new (...args: any[]) => Drawing, keyCmd: string, paths: string, rotate=false) {
        const elem = document.createElement('div')
        elem.classList.add("toolbox-button");

        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("width", "29");
        svg.setAttribute("height", "29");

        const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
        group.innerHTML = paths
        // 颜色交给 CSS（.toolbox-button g）：fill / color 用 var(--color)，
        // 这样深浅主题切换时图标描边/填充会跟着换，而不是永远用默认灰。

        svg.appendChild(group)
        elem.appendChild(svg);

        const icon: Icon = {div: elem, group: group, type: DrawingType}

        elem.addEventListener('click', () => this._onIconClick(icon));

        this._commandFunctions.push((event: KeyboardEvent) => {
            if (this._handlerID !== window.handlerInFocus) return false;

            if (event.altKey && event.code === keyCmd) {
                event.preventDefault()
                this._onIconClick(icon);
                return true
            }
            return false;
        })

        if (rotate == true) {
            svg.style.transform = 'rotate(90deg)';
            svg.style.transformBox = 'fill-box';
            svg.style.transformOrigin = 'center';
        }

        return elem
    }

    private _onIconClick(icon: Icon) {
        if (this.activeIcon) {

            this.activeIcon.div.classList.remove('active-toolbox-button');
            window.setCursor('crosshair');
            this._drawingTool?.stopDrawing()
            if (this.activeIcon === icon) {
                this.activeIcon = null
                return 
            }
        }
        this.activeIcon = icon
        this.activeIcon.div.classList.add('active-toolbox-button')
        window.setCursor('crosshair');
        this._drawingTool?.beginDrawing(this.activeIcon.type);
    }

    removeActiveAndSave = () => {
        window.setCursor('default');
        if (this.activeIcon) this.activeIcon.div.classList.remove('active-toolbox-button')
        this.activeIcon = null
        this.saveDrawings()
    }

    addNewDrawing(d: Drawing) {
        this._drawingTool.addNewDrawing(d);
    }

    clearDrawings() {
        this._drawingTool.clearDrawings();
    }

    saveDrawings = () => {
        const drawingMeta = []
        for (const d of this._drawingTool.drawings) {
            drawingMeta.push({
                type: d._type,
                points: d.points,
                options: d._options
            });
        }
        const string = JSON.stringify(drawingMeta);
        window.callbackFunction(`save_drawings${this._handlerID}_~_${string}`)
    }

    loadDrawings(drawings: any[]) { // TODO any
        // 保存格式：{type, points, options}。工具箱一共 13 种画线，之前这里
        // 只还原 5 种，斐波那契/测量/通道/仓位/叉形线/三角形/斐波那契扩展/
        // 江恩扇形会被静默丢弃。这里补齐全部类型，未知类型只告警不报错。
        const builders: Record<string, (points: any[], options: any) => Drawing> = {
            "TrendLine": (p, o) => new TrendLine(p[0], p[1], o),
            "Box": (p, o) => new Box(p[0], p[1], o),
            "HorizontalLine": (p, o) => new HorizontalLine(p[0], o),
            "RayLine": (p, o) => new RayLine(p[0], o),
            "VerticalLine": (p, o) => new VerticalLine(p[0], o),
            "FibonacciRetracement": (p, o) => new FibonacciRetracement(p[0], p[1], o),
            "FibonacciExtension": (p, o) => new FibonacciExtension(p[0], p[1], p[2], o),
            "Measure": (p, o) => new Measure(p[0], p[1], o),
            "ParallelChannel": (p, o) => new ParallelChannel(p[0], p[1], o),
            "Position": (p, o) => new Position(p[0], p[1], o),
            "AndrewsPitchfork": (p, o) => new AndrewsPitchfork(p[0], p[1], p[2], o),
            "Triangle": (p, o) => new Triangle(p[0], p[1], p[2], o),
            "GannFan": (p, o) => new GannFan(p[0], p[1], o),
        };

        drawings.forEach((d) => {
            const build = builders[d.type];
            if (!build) {
                console.warn('loadDrawings: unsupported drawing type', d.type);
                return;
            }
            try {
                this._drawingTool.addNewDrawing(build(d.points || [], d.options || {}));
            } catch (err) {
                console.warn('loadDrawings: failed to restore', d.type, err);
            }
        })

        // 存下来的是「时间 + bar 序号」，而 bar 序号只在保存它的那个周期里成立。
        // 切周期后（或换了一份数据后）必须按新周期的 bar 把序号重算一遍，否则画线
        // 会落在错误的位置。放在这里，恢复的入口就自带对齐。
        this._drawingTool.repositionOnTime();
    }
}
