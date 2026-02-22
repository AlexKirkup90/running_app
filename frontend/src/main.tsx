import React, { createContext, useContext, useState } from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom'
import { api, login } from './api'
import './index.css'

type Auth = { token: string; role: string; athlete_id?: number }
const Ctx = createContext<{auth?:Auth; setAuth:(a?:Auth)=>void}>({setAuth:()=>{}})
const useAuth = () => useContext(Ctx)

function LoginPage(){
  const {setAuth}=useAuth(); const [u,setU]=useState(''); const [p,setP]=useState(''); const [e,setE]=useState('')
  return <div className='p-8 max-w-md mx-auto'><h1 className='text-2xl mb-4'>Run Season Command</h1><input className='w-full p-2 text-black mb-2' placeholder='username' value={u} onChange={e=>setU(e.target.value)}/><input className='w-full p-2 text-black mb-2' placeholder='password' type='password' value={p} onChange={e=>setP(e.target.value)}/><button className='bg-indigo-600 px-3 py-2' onClick={async()=>{try{const t=await login(u,p); localStorage.setItem('token',t.access_token); localStorage.setItem('role',t.role); localStorage.setItem('athlete_id',String(t.athlete_id||'')); setAuth({token:t.access_token,role:t.role,athlete_id:t.athlete_id})}catch{setE('Invalid credentials')}}}>Sign in</button><div>{e}</div></div>
}

function CoachDashboard(){
  const {auth}=useAuth(); const [athletes,setAthletes]=React.useState<any[]>([])
  React.useEffect(()=>{api<any>('/athletes?status=active&offset=0&limit=20',{},auth?.token).then(r=>setAthletes(r.items))},[auth?.token])
  React.useEffect(()=>{const ws=new WebSocket('ws://localhost:8000/api/v1/ws/coach'); ws.onmessage=()=>api<any>('/athletes?status=active&offset=0&limit=20',{},auth?.token).then(r=>setAthletes(r.items)); return ()=>ws.close()},[auth?.token])
  return <div className='p-6'><h2 className='text-xl mb-3'>Coach Command Center</h2><ul>{athletes.map(a=><li key={a.id}>{a.first_name} {a.last_name} ({a.status})</li>)}</ul></div>
}

function AthletePage(){
  const {auth}=useAuth(); const [msg,setMsg]=useState('')
  const submitCheckin=async()=>{await api('/checkins',{method:'POST',body:JSON.stringify({sleep:4,energy:4,recovery:4,stress:2,training_today:true})},auth?.token);setMsg('Check-in submitted')}
  const submitLog=async()=>{await api('/training-logs',{method:'POST',body:JSON.stringify({session_category:'easy_run',duration_min:45,distance_km:8,avg_hr:145,max_hr:160,avg_pace_sec_per_km:335,rpe:5,notes:'solid',pain_flag:false})},auth?.token);setMsg('Session logged')}
  return <div className='p-6'><h2 className='text-xl mb-3'>Athlete Check-in & Session Logging</h2><div className='space-x-2'><button className='bg-emerald-600 px-3 py-2' onClick={submitCheckin}>Submit Check-in</button><button className='bg-sky-600 px-3 py-2' onClick={submitLog}>Log Session</button></div><p className='mt-3'>{msg}</p></div>
}

function App(){
  const [auth,setAuth]=useState<Auth|undefined>(()=>{const t=localStorage.getItem('token'); const r=localStorage.getItem('role'); if(!t||!r)return undefined; return {token:t,role:r,athlete_id:Number(localStorage.getItem('athlete_id')||undefined)}})
  return <Ctx.Provider value={{auth,setAuth}}><BrowserRouter><nav className='p-4 border-b border-slate-700'><Link to='/' className='mr-3'>Home</Link>{auth&&<button onClick={()=>{localStorage.clear();setAuth(undefined)}}>Logout</button>}</nav><Routes><Route path='/' element={!auth?<LoginPage/>:auth.role==='coach'?<CoachDashboard/>:<AthletePage/>}/><Route path='*' element={<Navigate to='/'/>}/></Routes></BrowserRouter></Ctx.Provider>
}

ReactDOM.createRoot(document.getElementById('root')!).render(<App />)
