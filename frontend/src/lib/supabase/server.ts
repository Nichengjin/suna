'use server';
import { createServerClient, type CookieOptions } from '@supabase/ssr';
import { cookies } from 'next/headers';

export const createClient = async () => {
  const cookieStore = await cookies();
  let supabaseUrl = 'https://uoptqsubepkyeepydjvc.supabase.co';
  const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVvcHRxc3ViZXBreWVlcHlkanZjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTA5Mzc0NjcsImV4cCI6MjA2NjUxMzQ2N30.BghfP2XYoTmD34mMrOprbUwfRARihZs_MHXuDRrdhvk';

  // Ensure the URL is in the proper format with http/https protocol
  // if (supabaseUrl && !supabaseUrl.startsWith('http')) {
  //   // If it's just a hostname without protocol, add http://
  //   supabaseUrl = `http://${supabaseUrl}`;
  // }

  console.log('[SERVER] Supabase URL:', supabaseUrl);
  console.log('[SERVER] Supabase Anon Key:', supabaseAnonKey);

  return createServerClient(supabaseUrl, supabaseAnonKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set({ name, value, ...options }),
          );
        } catch (error) {
          // The `set` method was called from a Server Component.
          // This can be ignored if you have middleware refreshing
          // user sessions.
        }
      },
    },
  });
};
