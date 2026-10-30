import {afterEach,expect,test,vi} from 'vitest'
const original=window.fetch

afterEach(()=>{window.fetch=original;vi.unstubAllGlobals();vi.resetModules();history.replaceState(null,'','/studio/');document.documentElement.classList.remove('is-design-preview')})

test('normal workspace never installs fixture transport',async()=>{
 history.replaceState(null,'','/studio/');const mock=vi.fn();window.fetch=mock
 const {installDesignPreview,isDesignPreview}=await import('../src/preview-api')
 installDesignPreview();expect(isDesignPreview()).toBe(false);expect(window.fetch).toBe(mock)
})
test('explicit preview returns sample data and blocks all real writes',async()=>{
 history.replaceState(null,'','/studio/?preview=1');const network=vi.fn();window.fetch=network
 const {installDesignPreview,previewHref}=await import('../src/preview-api');installDesignPreview()
 const read=await window.fetch('/api/tasks');expect((await read.json())[0].id).toBe('demo:1')
 const write=await window.fetch('/api/settings',{method:'POST',body:'{}'});expect(write.status).toBe(409);expect(network).not.toHaveBeenCalled()
 expect(previewHref('/studio/?task=demo:1&preview=1')).toBe('/studio/?task=demo%3A1&preview=1')
})
