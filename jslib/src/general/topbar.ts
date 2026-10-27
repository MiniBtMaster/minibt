import { GlobalParams } from "./global-params";
import { Handler } from "./handler";
import { Menu } from "./menu";

declare const window: GlobalParams

interface Widget {
    elem: HTMLDivElement;
    callbackName: string;
    intervalElements: HTMLButtonElement[];
    onItemClicked: Function;
    /** 只有 switcher 有：原地重建按钮行（见 `makeSwitcher`） */
    updateItems?: (items: string[], defaultItem?: string) => void;
}

export class TopBar {
    private _handler: Handler | undefined;
    public _div: HTMLDivElement;

    /** true for the page-level bar (`createPageTopBar`): it lives at the top of
     *  the window instead of inside a chart, and every chart gives up its
     *  height so the bar stays put when charts are added or laid out. */
    private _page: boolean = false;

    private static _pageBars: TopBar[] = [];

    private left: HTMLDivElement;
    private right: HTMLDivElement;

    constructor(handler?: Handler, page: boolean = false) {
        this._handler = handler;
        this._page = page;

        this._div = document.createElement('div');
        this._div.classList.add('topbar');

        const createTopBarContainer = (justification: string) => {
            const div = document.createElement('div')
            div.classList.add('topbar-container')
            div.style.justifyContent = justification
            this._div.appendChild(div)
            return div
        }
        this.left = createTopBarContainer('flex-start')
        this.right = createTopBarContainer('flex-end')
    }
    
    /** Combined height of the page-level bars (0 when there is none). */
    static pageHeight(): number {
        return TopBar._pageBars.reduce(
            (total, bar) => total + (bar._div.getBoundingClientRect().height || 0),
            0)
    }

    static registerPageBar(bar: TopBar) {
        TopBar._pageBars.push(bar)
    }

    makeSwitcher(items: string[], defaultItem: string, callbackName: string, align='left') {
        const switcherElement = document.createElement('div');
        switcherElement.style.margin = '4px 12px'

        let activeItemEl: HTMLButtonElement;
        // 重建选项时用它来决定哪个按钮高亮（切策略时第二层顶栏要换一批 K 线）
        let activeName = defaultItem;

        const createAndReturnSwitcherButton = (itemName: string) => {
            const button = document.createElement('button');
            button.classList.add('topbar-button');
            button.classList.add('switcher-button');
            button.style.margin = '0px 2px';
            button.innerText = itemName;

            if (itemName == activeName) {
                activeItemEl = button;
                button.classList.add('active-switcher-button');
            }

            const buttonWidth = TopBar.getClientWidth(button)
            button.style.minWidth = buttonWidth + 1 + 'px'
            button.addEventListener('click', () => widget.onItemClicked(button))

            switcherElement.appendChild(button);
            return button;
        }

        const widget: Widget = {
            elem: switcherElement,
            callbackName: callbackName,
            intervalElements: items.map(createAndReturnSwitcherButton),
            onItemClicked: (item: HTMLButtonElement) => {
                if (item == activeItemEl) return
                activeItemEl.classList.remove('active-switcher-button');
                item.classList.add('active-switcher-button');
                activeItemEl = item;
                window.callbackFunction(`${widget.callbackName}_~_${item.innerText}`);
            },
            // 动态换选项（`switcher` 的按钮行原地重建）：Python 侧
            // `SwitcherWidget.update_items()` 用它，用在"随策略切换的合约栏"上
            updateItems: (newItems: string[], defaultItem?: string) => {
                activeName = defaultItem ?? newItems[0];
                switcherElement.innerHTML = '';
                widget.intervalElements =
                    newItems.map(createAndReturnSwitcherButton);
            }
        }

        this.appendWidget(switcherElement, align, true)
        return widget
    }

    makeTextBoxWidget(text: string, align='left', callbackName=null) {
        if (callbackName) {
            const textBox = document.createElement('input');
            textBox.classList.add('topbar-textbox-input');
            textBox.value = text
            textBox.style.width = `${(textBox.value.length+2)}ch`
            textBox.addEventListener('focus', () => {
                window.textBoxFocused = true;
            })
            textBox.addEventListener('input', (e) => {
                e.preventDefault();
                textBox.style.width = `${(textBox.value.length+2)}ch`;
            });
            textBox.addEventListener('keydown', (e) => {
                if (e.key == 'Enter') {
                    e.preventDefault();
                    textBox.blur();
                }
            });
            textBox.addEventListener('blur', () => {
                window.callbackFunction(`${callbackName}_~_${textBox.value}`)
                window.textBoxFocused = false;
            });
            this.appendWidget(textBox, align, true)
            return textBox
        } else {
            const textBox = document.createElement('div');
            textBox.classList.add('topbar-textbox');
            textBox.innerText = text
            this.appendWidget(textBox, align, true)
            return textBox
        }
    }

    makeMenu(items: string[], activeItem: string, separator: boolean, callbackName: string, align: 'right'|'left') {
        return new Menu(this.makeButton.bind(this), callbackName, items, activeItem, separator, align)
    }

    makeButton(defaultText: string, callbackName: string | null, separator: boolean, append=true, align='left', toggle=false) {
        let button = document.createElement('button')
        button.classList.add('topbar-button');
        // button.style.color = window.pane.color
        button.innerText = defaultText;
        document.body.appendChild(button)
        button.style.minWidth = button.clientWidth+1+'px'
        document.body.removeChild(button)

        let widget = {
            elem: button,
            callbackName: callbackName
        }

        if (callbackName) {
            let handler;
            if (toggle) {
                let state = false;
                handler = () => {
                    state = !state
                    window.callbackFunction(`${widget.callbackName}_~_${state}`)
                    button.style.backgroundColor = state ? 'var(--active-bg-color)' : '';
                    button.style.color = state ? 'var(--active-color)' : '';
                }
            } else {
                handler = () => window.callbackFunction(`${widget.callbackName}_~_${button.innerText}`)
            }
            button.addEventListener('click', handler);
        }
        if (append) this.appendWidget(button, align, separator)
        return widget
    }

    makeSeparator(align='left') {
        const separator = document.createElement('div')
        separator.classList.add('topbar-seperator')
        const div = align == 'left' ? this.left : this.right
        div.appendChild(separator)
    }

    appendWidget(widget: HTMLElement, align: string, separator: boolean) {
        const div = align == 'left' ? this.left : this.right
        if (separator) {
            if (align == 'left') div.appendChild(widget)
            this.makeSeparator(align)
            if (align == 'right') div.appendChild(widget)
        } else div.appendChild(widget)
        this.reLayout();
    }

    /** The bar just changed size: everything below it has to make room. */
    private reLayout() {
        if (this._page) {
            Handler.reLayoutAll()
        } else {
            this._handler?.reSize()
        }
    }

    private static getClientWidth(element: HTMLElement) {
        document.body.appendChild(element);
        const width = element.clientWidth;
        document.body.removeChild(element);
        return width;
    }
}




/** Create the page-level top bar: it spans the whole window and sits above
 *  every chart (see `Window.page_topbar` in python). */
export function createPageTopBar(): TopBar {
    return Handler.createPageTopBar()
}
