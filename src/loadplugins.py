import config

import os
import sys

import gst

# Loaded plugins must be kept in a list in order to guarantee that
# they are not freed before the end of the execution of the whole
# program.
pluginList = []

# Search for all plugin files and try to register them.
for root, dirs, files in os.walk(config.gstPlugins):
   for file in files:
      if file[-len(config.pluginSuffix):] == config.pluginSuffix:
         plugin = gst.plugin_load_file(os.path.join(root, file))
         if plugin:
            pluginList.append(plugin)
            gst.registry_pool_add_plugin(plugin)

# Don't export any actual symbols.
__all__ = []
