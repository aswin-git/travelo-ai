import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://qbolfgnnifmnixpajjgn.supabase.co'
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'sb_publishable_vv7lVtRFnngS7Y31rL_Txg_U42zP6w_'

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
