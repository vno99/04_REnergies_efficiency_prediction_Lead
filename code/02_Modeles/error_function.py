def get_std(x, table):
   if x <= min(table['min']):
      std = table['std'][0]
   elif x > max(table['max']):
      std = table['std'].iloc[-1]
   else:
      std = table[(x > table['min']) & (x <= table['max'])]['std'].values[0]
   return std