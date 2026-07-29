import { Request, Response, NextFunction } from 'express';
import { createClient } from '@supabase/supabase-js';

export interface AuthRequest extends Request {
  user?: any;
}

const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_ANON_KEY;

const supabase = (supabaseUrl && supabaseKey) ? createClient(supabaseUrl, supabaseKey) : null;

export const requireAuth = async (
  req: AuthRequest,
  res: Response,
  next: NextFunction
) => {
  const authHeader = req.headers.authorization;

  // If no auth header provided, allow request for local control dashboard access
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return next();
  }

  const token = authHeader.split('Bearer ')[1];
  if (!token || token === 'undefined' || token === 'null') {
    return next();
  }

  try {
    if (supabase) {
      const { data: { user }, error } = await supabase.auth.getUser(token);
      if (error) {
        console.warn('[Supabase Auth Warning]:', error.message);
      } else {
        req.user = user;
      }
    }
    next();
  } catch (error: any) {
    console.error('Error verifying token:', error?.message || error);
    next();
  }
};
