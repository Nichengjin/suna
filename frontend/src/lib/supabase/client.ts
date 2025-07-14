import { createBrowserClient } from '@supabase/ssr';

export const createClient = () => {
  // Get URL and key from environment variables
  let supabaseUrl = 'https://uoptqsubepkyeepydjvc.supabase.co';
  const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVvcHRxc3ViZXBreWVlcHlkanZjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTA5Mzc0NjcsImV4cCI6MjA2NjUxMzQ2N30.BghfP2XYoTmD34mMrOprbUwfRARihZs_MHXuDRrdhvk';

  // Ensure the URL is in the proper format with http/https protocol
  if (supabaseUrl && !supabaseUrl.startsWith('http')) {
    // If it's just a hostname without protocol, add http://
    supabaseUrl = `http://${supabaseUrl}`;
  }

  // console.log('Supabase URL:', supabaseUrl);
  // console.log('Supabase Anon Key:', supabaseAnonKey);

  return createBrowserClient(supabaseUrl, supabaseAnonKey);
};
