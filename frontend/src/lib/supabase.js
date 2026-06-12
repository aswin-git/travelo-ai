import { createClient } from '@supabase/supabase-js'

const supabaseUrl = 'https://qbolfgnnifmnixpajjgn.supabase.co'
const supabaseAnonKey = 'sb_publishable_vv7lVtRFnngS7Y31rL_Txg_U42zP6w_'

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
