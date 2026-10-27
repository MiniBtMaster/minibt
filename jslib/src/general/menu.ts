import { GlobalParams } from "./global-params";

declare const window: GlobalParams

export class Menu {
    private div: HTMLDivElement;
    private isOpen: boolean = false;
    private widget: any;
    private activeItem: string;

    constructor(
        private makeButton: Function,
        private callbackName: string,
        items: string[],
        activeItem: string,
        separator: boolean,
        align: 'right'|'left') {

        this.div = document.createElement('div')
        this.div.classList.add('topbar-menu');

        this.activeItem = activeItem
        this.widget = this.makeButton(activeItem+' ↓', null, separator, true, align)

        this.updateMenuItems(items, activeItem)

        this.widget.elem.addEventListener('click', () => {
            this.isOpen = !this.isOpen;
            if (!this.isOpen) {
                this.div.style.display = 'none';
                return;
            }
            let rect = this.widget.elem.getBoundingClientRect()
            this.div.style.display = 'flex'
            this.div.style.flexDirection = 'column'

            let center = rect.x+(rect.width/2)
            this.div.style.left = center-(this.div.clientWidth/2)+'px'
            this.div.style.top = rect.y+rect.height+'px'
        })
        document.body.appendChild(this.div)
    }

    /** Rebuild the dropdown. `label` (used by the constructor) keeps a label
     *  such as '布局 ↓' that is not one of the items; otherwise the active item
     *  stays selected, falling back to the first item when it was dropped. */
    updateMenuItems(items: string[], label?: string) {
        this.div.innerHTML = '';

        items.forEach(text => {
            let button = this.makeButton(text, null, false, false)
            button.elem.addEventListener('click', () => {
                this._clickHandler(button.elem.innerText);
            });
            button.elem.style.margin = '4px 4px'
            button.elem.style.padding = '2px 2px'
            this.div.appendChild(button.elem)
        })
        const active = label !== undefined ? label
            : (items.includes(this.activeItem) ? this.activeItem : items[0])
        this.activeItem = active
        this.widget.elem.innerText = active+' ↓';
    }
    
    private _clickHandler(name: string) {
        this.activeItem = name
        this.widget.elem.innerText = name+' ↓'
        window.callbackFunction(`${this.callbackName}_~_${name}`)
        this.div.style.display = 'none'
        this.isOpen = false
    }
}