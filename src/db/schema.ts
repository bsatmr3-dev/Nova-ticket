import { pgTable, serial, text, integer, bigint, timestamp, uniqueIndex, index } from 'drizzle-orm/pg-core';

export const panels = pgTable('panels', {
  id: serial('id').primaryKey(),
  title: text('title').notNull(),
  description: text('description').notNull(),
  color: integer('color').default(3447003),
  imageUrl: text('image_url'),
  bannerUrl: text('banner_url'),
  thumbnailUrl: text('thumbnail_url'),
  footerText: text('footer_text'),
  channelId: bigint('channel_id', { mode: 'bigint' }),
  messageId: bigint('message_id', { mode: 'bigint' }),
  categoriesJson: text('categories_json').default('[]'),
});

export const tickets = pgTable('tickets', {
  id: serial('id').primaryKey(),
  guildId: bigint('guild_id', { mode: 'bigint' }).notNull(),
  channelId: bigint('channel_id', { mode: 'bigint' }).notNull().unique(),
  userId: bigint('user_id', { mode: 'bigint' }).notNull(),
  panelId: integer('panel_id').notNull(),
  categoryId: text('category_id').notNull(),
  status: text('status').default('open'),
  claimedBy: bigint('claimed_by', { mode: 'bigint' }),
  priority: text('priority').default('Medium'),
  department: text('department'),
  createdAt: text('created_at').notNull(),
  closedAt: text('closed_at'),
  firstResponseAt: text('first_response_at'),
  isHidden: integer('is_hidden').default(0),
  lastStaffMessageAt: text('last_staff_message_at'),
  memberResponded: integer('member_responded').default(1),
  categoryPoints: integer('category_points').default(0),
}, (table) => ({
  userStatusIdx: index('idx_tickets_user').on(table.userId, table.status),
  channelIdx: index('idx_tickets_channel').on(table.channelId),
}));

export const ratings = pgTable('ratings', {
  id: serial('id').primaryKey(),
  ticketId: integer('ticket_id').notNull(),
  userId: bigint('user_id', { mode: 'bigint' }).notNull(),
  staffId: bigint('staff_id', { mode: 'bigint' }).notNull(),
  stars: integer('stars').notNull(),
  feedback: text('feedback'),
  createdAt: text('created_at').notNull(),
}, (table) => ({
  staffIdx: index('idx_ratings_staff').on(table.staffId),
}));

export const blacklist = pgTable('blacklist', {
  userId: bigint('user_id', { mode: 'bigint' }).primaryKey(),
  reason: text('reason').notNull(),
  addedBy: bigint('added_by', { mode: 'bigint' }).notNull(),
  createdAt: text('created_at').notNull(),
});

export const guildSettings = pgTable('guild_settings', {
  guildId: bigint('guild_id', { mode: 'bigint' }).primaryKey(),
  logChannelId: bigint('log_channel_id', { mode: 'bigint' }),
  transcriptChannelId: bigint('transcript_channel_id', { mode: 'bigint' }),
  categoryId: bigint('category_id', { mode: 'bigint' }),
  ownerRoleId: bigint('owner_role_id', { mode: 'bigint' }),
  adminRoleId: bigint('admin_role_id', { mode: 'bigint' }),
  supportManagerRoleId: bigint('support_manager_role_id', { mode: 'bigint' }),
  seniorSupportRoleId: bigint('senior_support_role_id', { mode: 'bigint' }),
  supportRoleId: bigint('support_role_id', { mode: 'bigint' }),
  language: text('language').default('ar'),
  botToken: text('bot_token'),
});

export const internalNotes = pgTable('internal_notes', {
  id: serial('id').primaryKey(),
  ticketId: integer('ticket_id').notNull(),
  authorId: bigint('author_id', { mode: 'bigint' }).notNull(),
  content: text('content').notNull(),
  createdAt: text('created_at').notNull(),
}, (table) => ({
  ticketIdx: index('idx_notes_ticket').on(table.ticketId),
}));

export const wizardSessions = pgTable('wizard_sessions', {
  userId: bigint('user_id', { mode: 'bigint' }).primaryKey(),
  stateJson: text('state_json').notNull(),
  updatedAt: text('updated_at').notNull(),
});

export const settingsAuditLogs = pgTable('settings_audit_logs', {
  id: serial('id').primaryKey(),
  guildId: bigint('guild_id', { mode: 'bigint' }).notNull(),
  executorId: bigint('executor_id', { mode: 'bigint' }).notNull(),
  action: text('action').notNull(),
  details: text('details'),
  createdAt: text('created_at').notNull(),
});

export const actionPermissions = pgTable('action_permissions', {
  id: serial('id').primaryKey(),
  guildId: bigint('guild_id', { mode: 'bigint' }).notNull(),
  actionName: text('action_name').notNull(),
  minRank: integer('min_rank').default(10),
  allowedRolesJson: text('allowed_roles_json').default('[]'),
}, (table) => ({
  guildActionUnique: uniqueIndex('idx_action_permissions_guild_action').on(table.guildId, table.actionName),
}));

export const ticketAuditLogs = pgTable('ticket_audit_logs', {
  id: serial('id').primaryKey(),
  ticketId: integer('ticket_id').notNull(),
  action: text('action').notNull(),
  executorId: bigint('executor_id', { mode: 'bigint' }).notNull(),
  details: text('details'),
  createdAt: text('created_at').notNull(),
}, (table) => ({
  ticketIdx: index('idx_audit_ticket').on(table.ticketId),
}));

export const staffStats = pgTable('staff_stats', {
  guildId: bigint('guild_id', { mode: 'bigint' }).notNull(),
  userId: bigint('user_id', { mode: 'bigint' }).notNull(),
  points: integer('points').default(0),
  ticketsHandled: integer('tickets_handled').default(0),
  totalStars: integer('total_stars').default(0),
  totalRatings: integer('total_ratings').default(0),
});
