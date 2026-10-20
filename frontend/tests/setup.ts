import { vi, beforeEach } from 'vitest'
class ResizeObserver {observe(){}unobserve(){}disconnect(){}}
beforeEach(()=>vi.stubGlobal('ResizeObserver',ResizeObserver))
window.matchMedia=vi.fn().mockImplementation(()=>({matches:false,addEventListener(){},removeEventListener(){},addListener(){},removeListener(){}}))
Element.prototype.scrollIntoView=vi.fn()
Range.prototype.getClientRects=()=>({length:0,item:()=>null,[Symbol.iterator]:function*(){}} as DOMRectList)
Range.prototype.getBoundingClientRect=()=>new DOMRect()
