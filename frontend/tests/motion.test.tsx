import React from 'react'
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,expect,test,vi} from 'vitest'
import {MotionToast,CountUp,useReducedMotion} from '../src/Motion'
afterEach(()=>{cleanup();vi.useRealTimers();vi.unstubAllGlobals()})
test('toast pauses its three-second timeout while the user focuses it',()=>{
 vi.useFakeTimers();const close=vi.fn();render(<MotionToast message="保存完成" onClose={close}/>);act(()=>vi.advanceTimersByTime(2800));fireEvent.mouseEnter(screen.getByRole('status'));act(()=>vi.advanceTimersByTime(5000));expect(close).not.toHaveBeenCalled();fireEvent.mouseLeave(screen.getByRole('status'));act(()=>vi.advanceTimersByTime(200));expect(screen.getByRole('status').className).toContain('is-leaving');act(()=>vi.advanceTimersByTime(180));expect(close).toHaveBeenCalledTimes(1)
})
test('reduced motion changes live and exposes the final count to assistive technology',()=>{
 const listeners=new Set<()=>void>();const query={matches:false,addEventListener:vi.fn((_,fn)=>{listeners.add(fn)}),removeEventListener:vi.fn()};vi.stubGlobal('matchMedia',()=>query)
 function View(){const reduce=useReducedMotion();return <><span data-testid="preference">{String(reduce)}</span><CountUp value={45}/></>}
 const result=render(<View/>);expect(result.container.querySelector('.sr-only')?.textContent).toBe('45');act(()=>{query.matches=true;listeners.forEach(fn=>fn())});expect(screen.getByTestId('preference').textContent).toBe('true');expect(result.container.querySelector('.count-value')?.textContent).toBe('45');result.unmount();expect(query.removeEventListener).toHaveBeenCalled()
})
